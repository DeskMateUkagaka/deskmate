"""ChatInputWindow — transparent popup for text input."""

import logging

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.lib.commands import SlashCommand

logger = logging.getLogger(__name__)

# Connection status colours
_STATUS_COLORS = {
    "connected": "#4ec94e",
    "connecting": "#f0c060",
    "disconnected": "#e05050",
    "error": "#e05050",
}

# Maximum number of lines shown before the input stops growing
_MAX_INPUT_LINES = 6
_LINE_HEIGHT_PX = 22
_MIN_HEIGHT_PX = 44

# Autocomplete popup
_POPUP_MAX_ITEMS = 8
_POPUP_ITEM_HEIGHT = 36


class _AutocompletePopup(QWidget):
    """Floating popup that shows filtered slash command suggestions."""

    command_selected = Signal(object)  # SlashCommand

    def __init__(self, parent: QWidget):
        super().__init__(parent, Qt.WindowType.SubWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget {"
            "  background: rgba(40, 40, 45, 0.98);"
            "  border: 1px solid rgba(100, 100, 130, 0.5);"
            "  border-radius: 8px;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self._list = QListWidget(self)
        self._list.setStyleSheet(
            "QListWidget {"
            "  background: transparent;"
            "  border: none;"
            "  outline: none;"
            "}"
            "QListWidget::item {"
            "  padding: 4px 8px;"
            "  border-radius: 4px;"
            "  color: #e8e8f0;"
            "}"
            "QListWidget::item:selected {"
            "  background: rgba(100, 140, 220, 0.35);"
            "}"
            "QListWidget::item:hover {"
            "  background: rgba(100, 100, 130, 0.25);"
            "}"
        )
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        self._commands: list[SlashCommand] = []
        self.hide()

    def update_items(self, commands: list[SlashCommand]) -> None:
        """Populate list with filtered commands."""
        self._commands = commands
        self._list.clear()

        visible = commands[:_POPUP_MAX_ITEMS]
        for cmd in visible:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            # Rich-ish label: bold name + dim description
            label = QLabel(
                f"<b>{cmd.name}</b>  <span style='color: rgba(160,160,190,0.8); font-size: 11px;'>{cmd.description}</span>"
            )
            label.setStyleSheet("background: transparent; padding: 2px 4px;")
            label.setFont(QFont("Segoe UI", 10))
            item.setSizeHint(QSize(self._list.width(), _POPUP_ITEM_HEIGHT))
            self._list.addItem(item)
            self._list.setItemWidget(item, label)

        if visible:
            self._list.setCurrentRow(0)

        # Resize to fit items
        count = len(visible)
        h = count * _POPUP_ITEM_HEIGHT + 8  # margins
        self._list.setFixedHeight(h)
        self.adjustSize()

    def move_selection(self, delta: int) -> None:
        """Move selection up (-1) or down (+1)."""
        count = self._list.count()
        if count == 0:
            return
        current = self._list.currentRow()
        new_row = (current + delta) % count
        self._list.setCurrentRow(new_row)

    def accept_selection(self) -> SlashCommand | None:
        """Return the currently selected command, or None."""
        item = self._list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        cmd = item.data(Qt.ItemDataRole.UserRole)
        if cmd:
            self.command_selected.emit(cmd)


class _InputEdit(QTextEdit):
    """Single/multi-line text editor that:
    - Emits send_requested on Enter
    - Emits dismiss_requested on Escape
    - Adds a newline on Shift+Enter
    - Grows up to _MAX_INPUT_LINES rows, then scrolls
    - Delegates Up/Down/Tab/Enter to autocomplete when popup is active
    """

    send_requested = Signal(str)
    dismiss_requested = Signal()
    height_changed = Signal(int)
    text_changed_for_ac = Signal(str, int)  # (full text, cursor position)

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

        # Reference to the autocomplete popup (set by ChatInputWindow)
        self._popup: _AutocompletePopup | None = None

    def set_popup(self, popup: _AutocompletePopup) -> None:
        self._popup = popup

    def keyPressEvent(self, event: QKeyEvent) -> None:
        popup_active = self._popup is not None and self._popup.isVisible()

        if popup_active:
            key = event.key()
            if key == Qt.Key.Key_Up:
                self._popup.move_selection(-1)
                return
            if key == Qt.Key.Key_Down:
                self._popup.move_selection(1)
                return
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                cmd = self._popup.accept_selection()
                if cmd:
                    self._popup.command_selected.emit(cmd)
                return
            if key == Qt.Key.Key_Escape:
                self._popup.hide()
                return

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

        # Notify after key is processed so cursor position is updated
        cursor = self.textCursor()
        self.text_changed_for_ac.emit(self.toPlainText(), cursor.position())

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
    Typing '/' triggers slash command autocomplete.
    """

    message_sent = Signal(str)  # User pressed Enter with non-empty text
    dismissed = Signal()  # User pressed Escape
    resized = Signal(int, int)  # Content size changed (width, height)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._commands: list[SlashCommand] = []
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
        self._popup.hide()
        logger.debug("ChatInputWindow shown at (%d, %d)", pos.x(), pos.y())

    def hide_input(self) -> None:
        self._popup.hide()
        self.hide()
        logger.debug("ChatInputWindow hidden")

    def set_connection_status(self, status: str) -> None:
        """Update the connection indicator.  status: 'connected'|'connecting'|'disconnected'|'error'"""
        self._connection_status = status
        color = _STATUS_COLORS.get(status, _STATUS_COLORS["disconnected"])
        self._status_dot.set_color(color)
        self._status_label.setText(status.capitalize())
        logger.debug("Connection status: %s", status)

    def set_commands(self, commands: list[SlashCommand]) -> None:
        """Store slash commands for autocomplete."""
        self._commands = commands
        logger.debug("Loaded %d slash commands for autocomplete", len(commands))

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
        self._status_label.setStyleSheet("color: rgba(160,160,180,0.7); font-size: 11px;")
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
        self._editor.text_changed_for_ac.connect(self._on_text_changed_for_ac)
        self._editor.setPlaceholderText("Type a message…")
        root.addWidget(self._editor)

        # Autocomplete popup (child of this window, floats above editor)
        self._popup = _AutocompletePopup(self)
        self._popup.command_selected.connect(self._on_command_selected)
        self._editor.set_popup(self._popup)

    def _on_send(self, text: str) -> None:
        self._editor.clear()
        self._popup.hide()
        self.message_sent.emit(text)
        logger.debug("Message sent: %r", text[:80])

    def _on_dismiss(self) -> None:
        self.hide_input()
        self.dismissed.emit()

    def _on_editor_height_changed(self, _h: int) -> None:
        self._update_size()
        self._reposition_popup()

    def _update_size(self) -> None:
        self.adjustSize()
        w = max(self.sizeHint().width(), 400)
        # Force a fixed width so the window stays stable
        self.setFixedWidth(w)
        self.adjustSize()
        self.resized.emit(self.width(), self.height())

    # ------------------------------------------------------------------
    # Autocomplete
    # ------------------------------------------------------------------

    def _find_slash_trigger(self, text: str, cursor_pos: int) -> dict | None:
        """Search backwards from cursor for a '/' trigger.

        Stops at whitespace. Returns {"trigger_index": int, "filter_text": str}
        or None if no active trigger.
        """
        search_text = text[:cursor_pos]
        # Walk backwards until we hit whitespace or start of string
        i = len(search_text) - 1
        while i >= 0 and search_text[i] not in (" ", "\t", "\n"):
            i -= 1
        word_start = i + 1
        word = search_text[word_start:]
        if word.startswith("/"):
            return {"trigger_index": word_start, "filter_text": word}
        return None

    def _on_text_changed_for_ac(self, text: str, cursor_pos: int) -> None:
        """Called on each keypress — update autocomplete visibility."""
        if not self._commands:
            self._popup.hide()
            return

        trigger = self._find_slash_trigger(text, cursor_pos)
        if trigger is None:
            self._popup.hide()
            return

        filter_text = trigger["filter_text"].lower()
        filtered = [cmd for cmd in self._commands if cmd.name.lower().startswith(filter_text)]

        if not filtered:
            self._popup.hide()
            return

        self._popup.update_items(filtered)
        self._reposition_popup()
        self._popup.show()
        self._popup.raise_()

    def _reposition_popup(self) -> None:
        """Position popup just above the editor."""
        editor_geom = self._editor.geometry()
        popup_h = self._popup.sizeHint().height()
        popup_w = max(self.width() - 24, 300)
        self._popup.setFixedWidth(popup_w)
        x = editor_geom.left()
        y = editor_geom.top() - popup_h - 4
        self._popup.move(x, y)

    def _insert_command(self, cmd: SlashCommand) -> None:
        """Replace the current /partial trigger with cmd.name + space."""
        text = self._editor.toPlainText()
        cursor = self._editor.textCursor()
        cursor_pos = cursor.position()

        trigger = self._find_slash_trigger(text, cursor_pos)
        if trigger is None:
            return

        start = trigger["trigger_index"]
        # Replace from trigger start to cursor position with command + space
        new_text = text[:start] + cmd.name + " " + text[cursor_pos:]
        self._editor.setPlainText(new_text)

        # Move cursor to end of inserted command
        new_cursor_pos = start + len(cmd.name) + 1
        cursor = self._editor.textCursor()
        cursor.setPosition(new_cursor_pos)
        self._editor.setTextCursor(cursor)

    def _on_command_selected(self, cmd: SlashCommand) -> None:
        self._insert_command(cmd)
        self._popup.hide()
        self._editor.setFocus()
