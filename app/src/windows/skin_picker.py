"""SkinPickerWindow — grid of available skins with preview images."""

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.lib.skin import SkinInfo, SkinLoader

_CARD_SIZE = 140  # card width/height
_PREVIEW_SIZE = 120  # preview image size
_GRID_COLS = 3
_WINDOW_WIDTH = _GRID_COLS * (_CARD_SIZE + 10) + 40
_CARD_TEXT_HEIGHT = 36  # height reserved for name + author
_CARD_DESC_EXTRA = 14  # extra height when description is present


class _SkinCard(QWidget):
    """Single skin card: preview image + name + author + optional description."""

    clicked = Signal(str)  # emits skin_id

    def __init__(self, skin: SkinInfo, preview_path, is_selected: bool, parent=None):
        super().__init__(parent)
        self._skin_id = skin.id
        self._selected = is_selected
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        card_h = _CARD_SIZE + _CARD_TEXT_HEIGHT + (
            _CARD_DESC_EXTRA if skin.description else 0
        )
        self.setFixedSize(_CARD_SIZE, card_h)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 6)
        layout.setSpacing(4)

        # Preview image
        self._img_label = QLabel(self)
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setFixedSize(_PREVIEW_SIZE - 16, _PREVIEW_SIZE - 16)

        if preview_path:
            pix = QPixmap(str(preview_path))
            if not pix.isNull():
                pix = pix.scaled(
                    _PREVIEW_SIZE - 16,
                    _PREVIEW_SIZE - 16,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._img_label.setPixmap(pix)
            else:
                self._img_label.setText("?")
                self._img_label.setStyleSheet("color: #666; font-size: 24px;")
        else:
            self._img_label.setText("?")
            self._img_label.setStyleSheet("color: #666; font-size: 24px;")

        layout.addWidget(self._img_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Skin name
        name_label = QLabel(skin.name, self)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("color: #e8e8f0; font-size: 11px; font-weight: 500;")
        name_label.setMaximumWidth(_CARD_SIZE - 16)
        name_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(name_label)

        # Author
        if skin.author:
            author_label = QLabel(f"by {skin.author}", self)
            author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            author_label.setStyleSheet("color: #888; font-size: 10px;")
            author_label.setMaximumWidth(_CARD_SIZE - 16)
            layout.addWidget(author_label)

        # Description
        if skin.description:
            desc_label = QLabel(skin.description, self)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label.setStyleSheet("color: #666; font-size: 9px;")
            desc_label.setMaximumWidth(_CARD_SIZE - 16)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 10, 10)

        if self._selected:
            p.fillPath(path, QColor(80, 120, 220, 40))
            pen = QPen(QColor(80, 130, 220, 220))
        else:
            p.fillPath(path, QColor(45, 45, 55, 180))
            pen = QPen(QColor(100, 100, 130, 60))

        pen.setWidth(2)
        p.setPen(pen)
        p.drawPath(path)
        p.end()

    def mousePressEvent(self, _event) -> None:
        self.clicked.emit(self._skin_id)


class SkinPickerWindow(QWidget):
    """Grid of available skins with preview images."""

    skin_selected = Signal(str)  # emits selected skin_id

    def __init__(self, skin_loader: SkinLoader, parent=None):
        super().__init__(parent)
        self._skin_loader = skin_loader
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(_WINDOW_WIDTH)

        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_picker(self, skins: list[SkinInfo], current_skin_id: str) -> None:
        """Populate grid and show."""
        logger.debug(f"show_picker: {len(skins)} skins, current={current_skin_id}")
        self._current_skin_id = current_skin_id
        self._populate_grid(skins)
        logger.debug("show_picker: grid populated, adjusting size")
        self.adjustSize()
        logger.debug("show_picker: calling show()")
        self.show()
        logger.debug("show_picker: calling raise_()")
        self.raise_()
        logger.debug("show_picker: done")

    def hide_picker(self) -> None:
        self.hide()
        logger.debug("SkinPickerWindow hidden")

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        p.fillPath(path, QColor(28, 28, 34, 235))

        pen = QPen(QColor(100, 100, 130, 80))
        pen.setWidth(1)
        p.setPen(pen)
        p.drawPath(path)
        p.end()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide_picker()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 14)
        root.setSpacing(10)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(0)

        title = QLabel("Choose Skin", self)
        title.setStyleSheet("color: #e8e8f0; font-size: 14px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("×", self)
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  border: none;"
            "  color: #888;"
            "  font-size: 18px;"
            "  padding: 0;"
            "}"
            "QPushButton:hover { color: #ccc; }"
        )
        close_btn.clicked.connect(self.hide_picker)
        header.addWidget(close_btn)

        root.addLayout(header)

        # Scrollable grid area
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical {"
            "  background: rgba(255,255,255,0.05);"
            "  width: 6px;"
            "  border-radius: 3px;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: rgba(255,255,255,0.2);"
            "  border-radius: 3px;"
            "  min-height: 20px;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background: transparent;")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(10)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)

        self._scroll.setWidget(self._grid_container)
        root.addWidget(self._scroll)

        self._empty_label = QLabel("No skins installed", self)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #666; font-size: 13px; padding: 20px;")
        self._empty_label.hide()
        root.addWidget(self._empty_label)

    def _populate_grid(self, skins: list[SkinInfo]) -> None:
        # Clear existing cards
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not skins:
            self._scroll.hide()
            self._empty_label.show()
            self.setFixedHeight(120)
            return

        self._empty_label.hide()
        self._scroll.show()

        for idx, skin in enumerate(skins):
            preview_path = self._skin_loader.get_preview_image(skin.id)
            card = _SkinCard(
                skin, preview_path, skin.id == self._current_skin_id, self._grid_container
            )
            card.clicked.connect(self._on_card_clicked)
            row, col = divmod(idx, _GRID_COLS)
            self._grid_layout.addWidget(card, row, col)

        # Max 4 rows visible before scroll
        max_visible_rows = 4
        rows = (len(skins) + _GRID_COLS - 1) // _GRID_COLS
        visible_rows = min(rows, max_visible_rows)
        has_any_description = any(s.description for s in skins)
        card_h = _CARD_SIZE + _CARD_TEXT_HEIGHT + (
            _CARD_DESC_EXTRA if has_any_description else 0
        )
        scroll_h = visible_rows * (card_h + 10) + 10
        self._scroll.setFixedHeight(scroll_h)

    def _on_card_clicked(self, skin_id: str) -> None:
        logger.info(f"Skin selected: {skin_id}")
        self.skin_selected.emit(skin_id)
        self.hide_picker()
