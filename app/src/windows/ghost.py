"""GhostWindow — transparent window using QWebEngineView for browser-quality sprite rendering."""

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QSize, Qt, Signal, Slot, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

DEFAULT_HEIGHT = 540

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
</script>
</body>
</html>"""


class _GhostBridge(QObject):
    """QWebChannel bridge for JS -> Python callbacks (future use)."""

    def __init__(self, parent=None):
        super().__init__(parent)


class GhostWindow(QWidget):
    """Transparent window using QWebEngineView (Chromium) for the character sprite.

    Uses the browser's native image scaling (Lanczos/bicubic) for quality
    matching Tauri's WebKitGTK rendering.
    """

    position_changed = Signal(QPoint)
    clicked = Signal()
    expression_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Emotion -> [file paths]
        self._emotion_files: dict[str, list[Path]] = {}
        self._current_expr: str = "neutral"
        self._variant_indices: dict[str, int] = {}
        self._display_height: int = DEFAULT_HEIGHT
        self._skin_dir: Path | None = None
        self._idle_override_path: str | None = None

        # Drag state
        self._dragging = False
        self._drag_offset = QPoint()
        self._drag_moved = False

        # Track current image's natural size for image_bounds
        self._img_width = 0
        self._img_height = 0

        # WebEngineView setup
        self._web = QWebEngineView(self)
        page = QWebEnginePage(self._web)
        page.setBackgroundColor(QColor(0, 0, 0, 0))
        self._web.setPage(page)
        self._web.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._web.setStyleSheet("background: transparent;")
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, False)
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        # Web channel
        self._bridge = _GhostBridge(self)
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
        if ok and self._skin_dir:
            self._update_image()

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
                    logger.warning("Skin asset not found: %s", p)
            if paths:
                self._emotion_files[expr] = paths
                self._variant_indices[expr] = 0

        if not self._emotion_files:
            logger.error("No skin assets loaded from %s", skin_dir)
            return

        self._current_expr = next(
            (e for e in ("neutral", "connecting") if e in self._emotion_files),
            next(iter(self._emotion_files)),
        )

        # Compute display dimensions from first image
        self._compute_display_size()
        self._update_image()
        logger.info("Skin loaded: %d expressions from %s", len(self._emotion_files), skin_dir)

    def set_expression(self, name: str) -> None:
        if name not in self._emotion_files:
            name = "neutral" if "neutral" in self._emotion_files else next(iter(self._emotion_files), "")
        if not name or name == self._current_expr:
            return
        self._current_expr = name
        self._idle_override_path = None
        self._update_image()
        self.expression_changed.emit(name)

    def set_height(self, pixels: int) -> None:
        self._display_height = pixels
        self._compute_display_size()
        self._update_image()

    def save_position(self) -> tuple[float, float]:
        pos = self.pos()
        return float(pos.x()), float(pos.y())

    def restore_position(self, x: float, y: float) -> None:
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
        return {
            "centerX": x + w // 2,
            "centerY": y + h // 2,
            "top": y,
            "bottom": y + h,
            "left": x,
            "right": x + w,
        }

    # ------------------------------------------------------------------
    # Qt overrides — drag + click
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_moved = False
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self._drag_moved = True
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self.position_changed.emit(self.pos())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            if not self._drag_moved:
                self.clicked.emit()
            else:
                self.position_changed.emit(self.pos())

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
        from PySide6.QtGui import QPixmap
        pm = QPixmap(str(path))
        if pm.isNull():
            return
        ratio = pm.width() / pm.height()
        self._img_height = self._display_height
        self._img_width = max(1, round(self._display_height * ratio))
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
