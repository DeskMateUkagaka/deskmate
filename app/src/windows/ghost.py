"""GhostWindow — transparent frameless window displaying the character sprite."""

import logging
from pathlib import Path

import yaml

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

logger = logging.getLogger(__name__)

DEFAULT_HEIGHT = 540


class GhostWindow(QWidget):
    """Transparent frameless window displaying the character sprite.

    The window uses CompositionMode_Clear + SourceOver to paint the sprite
    without bleed artifacts — no WebKitGTK nudge workarounds needed.
    """

    position_changed = Signal(QPoint)   # emitted after each drag step and on release
    clicked = Signal()                   # emitted on left-click (open chat input)
    expression_changed = Signal(str)     # emitted when expression switches

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._pixmaps: dict[str, list[QPixmap]] = {}
        self._current_expr: str = "neutral"
        self._variant_indices: dict[str, int] = {}

        self._dragging = False
        self._drag_offset = QPoint()
        self._drag_moved = False   # track whether the mouse actually moved

        self._display_height = DEFAULT_HEIGHT

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_skin(self, emotions_map: dict[str, list[str]], skin_dir: Path) -> None:
        """Load all emotion pixmaps.

        emotions_map: {emotion_name: [filename, ...]} mapping
        skin_dir: directory containing the PNG files
        """
        self._pixmaps.clear()
        self._variant_indices.clear()

        emotions = emotions_map
        for expr, files in emotions.items():
            if isinstance(files, str):
                files = [files]
            loaded: list[QPixmap] = []
            for fname in files:
                path = skin_dir / fname
                if not path.exists():
                    logger.warning("Skin asset not found: %s", path)
                    continue
                pm = QPixmap(str(path))
                if pm.isNull():
                    logger.warning("Failed to load pixmap: %s", path)
                    continue
                scaled = pm.scaledToHeight(
                    self._display_height,
                    Qt.TransformationMode.SmoothTransformation,
                )
                loaded.append(scaled)
                logger.debug(
                    "Loaded %s/%s: %dx%d -> %dx%d",
                    expr, fname, pm.width(), pm.height(),
                    scaled.width(), scaled.height(),
                )
            if loaded:
                self._pixmaps[expr] = loaded
                self._variant_indices[expr] = 0

        if not self._pixmaps:
            logger.error("No skin assets loaded from %s", skin_dir)
            return

        self._current_expr = next(
            (e for e in ("neutral", "connecting") if e in self._pixmaps),
            next(iter(self._pixmaps)),
        )
        self._resize_to_current()
        logger.info(
            "Skin loaded: %d expressions from %s", len(self._pixmaps), skin_dir
        )

    def set_expression(self, name: str) -> None:
        """Switch to a named expression.  Falls back to 'neutral' if unknown."""
        if name not in self._pixmaps:
            logger.debug("Expression %r not found, falling back to neutral", name)
            name = "neutral" if "neutral" in self._pixmaps else next(iter(self._pixmaps), "")
        if not name:
            return
        if name != self._current_expr:
            self._current_expr = name
            self.update()
            self.expression_changed.emit(name)
            logger.debug("Expression -> %s", name)

    def set_height(self, pixels: int) -> None:
        """Resize all loaded pixmaps to the given height, maintaining aspect ratio."""
        self._display_height = pixels
        # Reload all scaled pixmaps in-place
        for expr, pms in list(self._pixmaps.items()):
            self._pixmaps[expr] = [
                pm.scaledToHeight(pixels, Qt.TransformationMode.SmoothTransformation)
                for pm in pms
            ]
        self._resize_to_current()

    def save_position(self) -> tuple[float, float]:
        """Return current window position as (x, y) floats for persistence."""
        pos = self.pos()
        return float(pos.x()), float(pos.y())

    def restore_position(self, x: float, y: float) -> None:
        """Move window to saved position."""
        self.move(int(x), int(y))

    def current_expression(self) -> str:
        return self._current_expr

    def image_bounds(self) -> dict:
        """Return the bounds of the visible sprite within the window.

        Returns a dict with keys: centerX, centerY, top, bottom, left, right
        (all in widget-local logical pixels).
        """
        pm = self._current_pixmap()
        if pm is None:
            return {"centerX": 0, "centerY": 0, "top": 0, "bottom": 0, "left": 0, "right": 0}
        x = (self.width() - pm.width()) // 2
        y = (self.height() - pm.height()) // 2
        return {
            "centerX": x + pm.width() // 2,
            "centerY": y + pm.height() // 2,
            "top": y,
            "bottom": y + pm.height(),
            "left": x,
            "right": x + pm.width(),
        }

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Clear to fully transparent first — prevents bleed on native Qt windows
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        pm = self._current_pixmap()
        if pm is not None:
            x = (self.width() - pm.width()) // 2
            y = (self.height() - pm.height()) // 2
            painter.drawPixmap(x, y, pm)

        painter.end()

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
    # Internal helpers
    # ------------------------------------------------------------------

    def _current_pixmap(self) -> QPixmap | None:
        variants = self._pixmaps.get(self._current_expr)
        if not variants:
            return None
        idx = self._variant_indices.get(self._current_expr, 0)
        return variants[idx % len(variants)]

    def _resize_to_current(self) -> None:
        pm = self._current_pixmap()
        if pm is not None:
            # Add a small margin so the sprite isn't clipped
            self.resize(pm.width() + 20, pm.height() + 20)
