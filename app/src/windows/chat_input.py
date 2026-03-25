"""ChatInputWindow — transparent popup for text input."""

import logging

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Connection status colours
_STATUS_COLORS = {
    "connected":    "#4ec94e",
    "connecting":   "#f0c060",
    "disconnected": "#e05050",
    "error":        "#e05050",
}

# Maximum number of lines shown before the input stops growing
_MAX_INPUT_LINES = 6
_LINE_HEIGHT_PX = 22
_MIN_HEIGHT_PX = 44


class _InputEdit(QTextEdit):
    """Single/multi-line text editor that:
    - Emits send_requested on Enter
    - Emits dismiss_requested on Escape
    - Adds a newline on Shift+Enter
    - Grows up to _MAX_INPUT_LINES rows, then scrolls
    """

    send_requested = Signal(str)
    dismiss_requested = Signal()
    height_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrapMode(
            self.wordWrapMode()  # keep default word-wrap
        )
        self.setStyleSheet(
            "QTextEdit {"
            "  background: transparent;"
            "  border: none;"
            "  color: #e8e8f0;"
            "  font-size: 14px;"
            "  padding: 0;"
            "  selection-background-color: rgba(100, 140, 220, 0.4);"
            "}"
        )
        font = QFont("Segoe UI", 10)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        self.setFont(font)
        self.document().contentsChanged.connect(self._on_contents_changed)
        self._update_height()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)  # newline
            else:
                text = self.toPlainText().strip()
                if text:
                    self.send_requested.emit(text)
            return
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss_requested.emit()
            return
        super().keyPressEvent(event)

    def _on_contents_changed(self) -> None:
        self._update_height()

    def _update_height(self) -> None:
        doc = self.document()
        doc.setTextWidth(self.viewport().width() or 400)
        lines = max(1, doc.blockCount())
        # clamp
        visible_lines = min(lines, _MAX_INPUT_LINES)
        h = max(_MIN_HEIGHT_PX, visible_lines * _LINE_HEIGHT_PX + 8)
        self.setFixedHeight(h)
        self.height_changed.emit(h)


class _StatusDot(QWidget):
    """Small coloured circle indicating connection status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor(_STATUS_COLORS["disconnected"])
        self.setFixedSize(8, 8)

    def set_color(self, hex_color: str) -> None:
        self._color = QColor(hex_color)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(self._color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(self.rect())
        p.end()


class ChatInputWindow(QWidget):
    """Transparent frameless popup window for chat text input.

    Keyboard behaviour:
    - Enter       → send message (message_sent signal)
    - Shift+Enter → newline
    - Escape      → dismiss (dismissed signal)

    The window auto-grows as the user types, up to _MAX_INPUT_LINES rows.
    """

    message_sent = Signal(str)       # User pressed Enter with non-empty text
    dismissed = Signal()             # User pressed Escape
    resized = Signal(int, int)       # Content size changed (width, height)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._commands: list[dict] = []
        self._connection_status = "disconnected"

        self._build_ui()
        self._update_size()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_input(self, pos: QPoint) -> None:
        """Show the input window at the given screen position and focus it."""
        self.move(pos)
        self.show()
        self._editor.setFocus()
        self._editor.clear()
        logger.debug("ChatInputWindow shown at (%d, %d)", pos.x(), pos.y())

    def hide_input(self) -> None:
        self.hide()
        logger.debug("ChatInputWindow hidden")

    def set_connection_status(self, status: str) -> None:
        """Update the connection indicator.  status: 'connected'|'connecting'|'disconnected'|'error'"""
        self._connection_status = status
        color = _STATUS_COLORS.get(status, _STATUS_COLORS["disconnected"])
        self._status_dot.set_color(color)
        self._status_label.setText(status.capitalize())
        logger.debug("Connection status: %s", status)

    def set_commands(self, commands: list[dict]) -> None:
        """Store slash commands for future autocomplete support."""
        self._commands = commands

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Clear to transparent
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # Dark rounded card
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        p.fillPath(path, QColor(28, 28, 34, 230))

        # Subtle border
        pen = QPen(QColor(100, 100, 130, 80))
        pen.setWidth(1)
        p.setPen(pen)
        p.drawPath(path)

        p.end()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(4)

        # Status bar row
        status_row = QHBoxLayout()
        status_row.setSpacing(5)
        status_row.setContentsMargins(0, 0, 0, 0)

        self._status_dot = _StatusDot(self)
        self._status_label = QLabel("Disconnected", self)
        self._status_label.setStyleSheet(
            "color: rgba(160,160,180,0.7); font-size: 11px;"
        )
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_label)
        status_row.addStretch()

        hint = QLabel("Enter to send · Shift+Enter for newline · Esc to close", self)
        hint.setStyleSheet("color: rgba(120,120,140,0.55); font-size: 10px;")
        status_row.addWidget(hint)

        root.addLayout(status_row)

        # Text editor
        self._editor = _InputEdit(self)
        self._editor.send_requested.connect(self._on_send)
        self._editor.dismiss_requested.connect(self._on_dismiss)
        self._editor.height_changed.connect(self._on_editor_height_changed)
        self._editor.setPlaceholderText("Type a message…")
        root.addWidget(self._editor)

    def _on_send(self, text: str) -> None:
        self._editor.clear()
        self.message_sent.emit(text)
        logger.debug("Message sent: %r", text[:80])

    def _on_dismiss(self) -> None:
        self.hide_input()
        self.dismissed.emit()

    def _on_editor_height_changed(self, _h: int) -> None:
        self._update_size()

    def _update_size(self) -> None:
        self.adjustSize()
        w = max(self.sizeHint().width(), 400)
        # Force a fixed width so the window stays stable
        self.setFixedWidth(w)
        self.adjustSize()
        self.resized.emit(self.width(), self.height())
