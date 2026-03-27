"""GhostWindow — transparent window using QWebEngineView for browser-quality sprite rendering."""

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.lib.compositor import get_window_position, set_window_position
from src.lib.consts import DEFAULT_GHOST_HEIGHT

GHOST_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body {
    background: transparent;
    overflow: hidden;
    width: 100vw;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    user-select: none;
    -webkit-user-select: none;
}
#sprite {
    image-rendering: auto; /* browser's best quality (Lanczos/bicubic) */
    pointer-events: none;
}
</style>
</head>
<body>
<img id="sprite" src="" />
<script>
let bridge = null;
new QWebChannel(qt.webChannelTransport, function(channel) {
    bridge = channel.objects.bridge;
});

function setImage(url, width, height) {
    const img = document.getElementById('sprite');
    img.src = url;
    img.width = width;
    img.height = height;
}

function getImageSize() {
    const img = document.getElementById('sprite');
    return JSON.stringify({width: img.naturalWidth, height: img.naturalHeight});
}

document.addEventListener('keydown', function(e) {
    if ((e.key === 'Escape' || e.key === 'x' || e.key === 'X') && bridge) {
        bridge.onDismissRequested();
    }
});
</script>
</body>
</html>"""


class _GhostBridge(QObject):
    """QWebChannel bridge for JS -> Python callbacks."""

    dismiss_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

    @Slot()
    def onDismissRequested(self):
        self.dismiss_requested.emit()


class GhostWindow(QWidget):
    """Transparent window using QWebEngineView (Chromium) for the character sprite.

    Uses the browser's native image scaling (Lanczos/bicubic) for quality
    matching Tauri's WebKitGTK rendering.
    """

    position_changed = Signal(QPoint)
    clicked = Signal()
    context_menu_requested = Signal(QPoint)
    dismiss_requested = Signal()
    expression_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("deskmate-ghost")

        # Emotion -> [file paths]
        self._emotion_files: dict[str, list[Path]] = {}
        self._current_expr: str = "neutral"
        self._variant_indices: dict[str, int] = {}
        self._display_height: int | None = DEFAULT_GHOST_HEIGHT
        self._display_width: int | None = None
        self._skin_dir: Path | None = None
        self._idle_override_path: str | None = None

        # Drag/click detection
        self._press_pos: QPoint | None = None
        self._dragging = False

        # Track current image size for image_bounds
        self._img_width = 0
        self._img_height = 0
        self._natural_height = 0  # original PNG height, for computing scale

        # WebEngineView setup
        self._web = QWebEngineView(self)
        page = QWebEnginePage(self._web)
        page.setBackgroundColor(QColor(0, 0, 0, 0))
        self._web.setPage(page)
        self._web.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._web.setStyleSheet("background: transparent;")
        # Install event filter to intercept mouse events from QWebEngineView's
        # internal child widgets (RenderWidgetHostViewQtDelegateWidget etc.)
        self._web.installEventFilter(self)
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, False)
        page.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )

        # Web channel
        self._bridge = _GhostBridge(self)
        self._bridge.dismiss_requested.connect(self.dismiss_requested)
        channel = QWebChannel(page)
        channel.registerObject("bridge", self._bridge)
        page.setWebChannel(channel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._web)

        # Use file:// base URL so <img src="file:///..."> works
        self._web.setHtml(GHOST_HTML, QUrl("file:///"))
        self._page_loaded = False
        self._web.loadFinished.connect(self._on_page_loaded)

    def _on_page_loaded(self, ok: bool) -> None:
        self._page_loaded = ok
        if ok:
            # QWebEngineView creates its render widget asynchronously —
            # install event filter on ALL descendants to capture mouse events
            self._install_filters_recursive(self._web)
            if self._skin_dir:
                self._update_image()

    def _install_filters_recursive(self, widget) -> None:
        """Install event filter on widget and all its children, recursively."""
        widget.installEventFilter(self)
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_skin(self, emotions_map: dict[str, list[str]], skin_dir: Path) -> None:
        """Load emotion file mappings."""
        self._emotion_files.clear()
        self._variant_indices.clear()
        self._skin_dir = skin_dir

        for expr, files in emotions_map.items():
            if isinstance(files, str):
                files = [files]
            paths = []
            for fname in files:
                p = skin_dir / fname
                if p.exists():
                    paths.append(p)
                else:
                    logger.warning(f"Skin asset not found: {p}")
            if paths:
                self._emotion_files[expr] = paths
                self._variant_indices[expr] = 0

        if not self._emotion_files:
            logger.error(f"No skin assets loaded from {skin_dir}")
            return

        self._current_expr = next(
            (e for e in ("neutral", "connecting") if e in self._emotion_files),
            next(iter(self._emotion_files)),
        )

        # Compute display dimensions from first image
        self._compute_display_size()
        self._update_image()
        logger.info(f"Skin loaded: {len(self._emotion_files)} expressions from {skin_dir}")

    def set_expression(self, name: str) -> None:
        if name not in self._emotion_files:
            name = (
                "neutral"
                if "neutral" in self._emotion_files
                else next(iter(self._emotion_files), "")
            )
        if not name or name == self._current_expr:
            return
        self._current_expr = name
        self._idle_override_path = None
        self._update_image()
        self.expression_changed.emit(name)

    def set_height(self, pixels: int | None) -> None:
        """Set target display height (mutually exclusive with set_width)."""
        if pixels is None:
            return
        self._display_height = pixels
        self._display_width = None
        self._compute_display_size()
        self._update_image()

    def set_width(self, pixels: int | None) -> None:
        """Set target display width (mutually exclusive with set_height)."""
        if pixels is None:
            return
        self._display_width = pixels
        self._display_height = None
        self._compute_display_size()
        self._update_image()

    def save_position(self) -> tuple[float, float]:
        pos = get_window_position(title="deskmate-ghost")
        if pos:
            return pos
        pos = self.pos()
        return float(pos.x()), float(pos.y())

    def restore_position(self, x: float, y: float) -> None:
        if set_window_position(title="deskmate-ghost", x=int(x), y=int(y)):
            return
        self.move(int(x), int(y))

    def current_expression(self) -> str:
        return self._current_expr

    def set_idle_override(self, path: str) -> None:
        self._idle_override_path = path
        self._update_image()

    def clear_idle_override(self) -> None:
        self._idle_override_path = None
        self._update_image()

    def image_bounds(self) -> dict:
        w = self._img_width
        h = self._img_height
        x = (self.width() - w) // 2
        y = (self.height() - h) // 2
        nh = self._natural_height
        return {
            "centerX": x + w // 2,
            "centerY": y + h // 2,
            "top": y,
            "bottom": y + h,
            "left": x,
            "right": x + w,
            "scale": h / nh if nh > 0 else 1.0,
        }

    # ------------------------------------------------------------------
    # Qt overrides — drag + click via event filter
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        """Intercept mouse events from QWebEngineView's internal child widgets."""
        etype = event.type()
        if etype == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._press_pos = event.globalPosition().toPoint()
                self._dragging = False
                return True
            if event.button() == Qt.MouseButton.RightButton:
                self.context_menu_requested.emit(event.globalPosition().toPoint())
                return True
        elif etype == QEvent.Type.MouseMove:
            if self._press_pos and not self._dragging:
                delta = (event.globalPosition().toPoint() - self._press_pos).manhattanLength()
                if delta >= 5:
                    self._dragging = True
                    self.windowHandle().startSystemMove()
                return True
        elif etype == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                if self._dragging:
                    self.position_changed.emit(self.pos())
                else:
                    self.clicked.emit()
                self._press_pos = None
                self._dragging = False
                return True
        elif etype == QEvent.Type.ChildAdded:
            child = event.child()
            if hasattr(child, "installEventFilter"):
                child.installEventFilter(self)
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _current_image_path(self) -> Path | None:
        if self._idle_override_path:
            return Path(self._idle_override_path)
        variants = self._emotion_files.get(self._current_expr)
        if not variants:
            return None
        idx = self._variant_indices.get(self._current_expr, 0)
        return variants[idx % len(variants)]

    def _compute_display_size(self) -> None:
        """Compute the display width/height from the first image's aspect ratio."""
        path = self._current_image_path()
        if not path or not path.exists():
            return
        pm = QPixmap(str(path))
        if pm.isNull():
            return
        self._natural_height = pm.height()
        ratio = pm.width() / pm.height()
        if self._display_width is not None:
            self._img_width = self._display_width
            self._img_height = max(1, round(self._display_width / ratio))
        else:
            self._img_height = self._display_height or DEFAULT_GHOST_HEIGHT
            self._img_width = max(1, round(self._img_height * ratio))
        # Window size = image size + small margin
        self.resize(self._img_width + 20, self._img_height + 20)

    def _update_image(self) -> None:
        if not self._page_loaded:
            return
        path = self._current_image_path()
        if not path:
            return
        url = QUrl.fromLocalFile(str(path.resolve())).toString()
        self._compute_display_size()
        js = f"setImage({_js_str(url)}, {self._img_width}, {self._img_height});"
        self._web.page().runJavaScript(js)


def _js_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
