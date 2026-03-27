"""SettingsWindow — dark-themed settings panel as a separate window."""

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.lib.settings import Settings

# Stylesheet constants for dark theme form elements
_INPUT_STYLE = (
    "QLineEdit, QSpinBox, QComboBox {"
    "  background: rgba(255,255,255,0.07);"
    "  color: #e8e8f0;"
    "  border: 1px solid rgba(255,255,255,0.15);"
    "  border-radius: 6px;"
    "  padding: 5px 8px;"
    "  font-size: 13px;"
    "}"
    "QLineEdit:focus, QSpinBox:focus, QComboBox:focus {"
    "  border: 1px solid rgba(100,140,220,0.6);"
    "  background: rgba(255,255,255,0.10);"
    "}"
    "QSpinBox::up-button, QSpinBox::down-button {"
    "  width: 16px;"
    "  background: rgba(255,255,255,0.08);"
    "  border: none;"
    "}"
    "QComboBox::drop-down {"
    "  border: none;"
    "  width: 20px;"
    "}"
    "QComboBox QAbstractItemView {"
    "  background: #2a2a32;"
    "  color: #e8e8f0;"
    "  selection-background-color: rgba(100,140,220,0.4);"
    "  border: 1px solid rgba(255,255,255,0.15);"
    "}"
)

_LABEL_STYLE = "color: rgba(200,200,220,0.85); font-size: 12px;"
_SECTION_STYLE = (
    "color: rgba(140,160,200,0.7); font-size: 11px; font-weight: 600; letter-spacing: 0.5px;"
)
_SAVE_BTN_STYLE = (
    "QPushButton {"
    "  background: #3060c0;"
    "  color: #fff;"
    "  border: none;"
    "  border-radius: 7px;"
    "  padding: 7px 20px;"
    "  font-size: 13px;"
    "  font-weight: 600;"
    "}"
    "QPushButton:hover { background: #3a70d0; }"
    "QPushButton:pressed { background: #2850a0; }"
)
_CANCEL_BTN_STYLE = (
    "QPushButton {"
    "  background: rgba(255,255,255,0.09);"
    "  color: #bbb;"
    "  border: none;"
    "  border-radius: 7px;"
    "  padding: 7px 20px;"
    "  font-size: 13px;"
    "}"
    "QPushButton:hover { background: rgba(255,255,255,0.14); }"
    "QPushButton:pressed { background: rgba(255,255,255,0.05); }"
)


class SettingsWindow(QWidget):
    """Settings panel as a separate transparent-ish window.

    Signals:
        settings_saved(dict): emitted when the user clicks Save; payload is
            the updated Settings fields as a plain dict.
    """

    settings_saved = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(360)

        font = QFont("Segoe UI", 10)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        self.setFont(font)

        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_settings(self, settings: Settings, skins: list[str]) -> None:
        """Populate form fields from settings and show the window."""
        self._gateway_url.setText(settings.gateway_url)
        self._gateway_token.setText(settings.gateway_token)
        self._bubble_timeout.setValue(round(settings.bubble_timeout_ms / 1000))
        self._ghost_height.setValue(settings.ghost_height_pixels)
        self._idle_interval.setValue(int(settings.idle_interval_seconds))

        self._skin_combo.clear()
        for skin_id in skins:
            self._skin_combo.addItem(skin_id)
        idx = self._skin_combo.findText(settings.current_skin_id)
        if idx >= 0:
            self._skin_combo.setCurrentIndex(idx)

        self.show()
        self.raise_()
        self.activateWindow()
        logger.debug("SettingsWindow shown")

    def hide_settings(self) -> None:
        self.hide()
        logger.debug("SettingsWindow hidden")

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Clear to transparent first
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # Dark solid card with rounded corners
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        p.fillPath(path, QColor(30, 30, 35, 242))  # rgba(30,30,35,0.95)

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
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # Title row
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Settings", self)
        title.setStyleSheet("color: #e8e8f0; font-size: 15px; font-weight: 600;")
        title_row.addWidget(title)
        title_row.addStretch()
        root.addLayout(title_row)

        # --- Section: Gateway ---
        gw_section = QLabel("GATEWAY", self)
        gw_section.setStyleSheet(_SECTION_STYLE)
        root.addWidget(gw_section)

        gw_form = QFormLayout()
        gw_form.setContentsMargins(0, 0, 0, 0)
        gw_form.setSpacing(6)
        gw_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._gateway_url = QLineEdit(self)
        self._gateway_url.setPlaceholderText("ws://localhost:18789")
        self._gateway_url.setStyleSheet(_INPUT_STYLE)

        self._gateway_token = QLineEdit(self)
        self._gateway_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._gateway_token.setPlaceholderText("token")
        self._gateway_token.setStyleSheet(_INPUT_STYLE)

        url_label = QLabel("URL", self)
        url_label.setStyleSheet(_LABEL_STYLE)
        token_label = QLabel("Token", self)
        token_label.setStyleSheet(_LABEL_STYLE)

        gw_form.addRow(url_label, self._gateway_url)
        gw_form.addRow(token_label, self._gateway_token)
        root.addLayout(gw_form)

        # --- Section: Appearance ---
        app_section = QLabel("APPEARANCE", self)
        app_section.setStyleSheet(_SECTION_STYLE)
        root.addWidget(app_section)

        app_form = QFormLayout()
        app_form.setContentsMargins(0, 0, 0, 0)
        app_form.setSpacing(6)
        app_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._ghost_height = QSpinBox(self)
        self._ghost_height.setRange(100, 1000)
        self._ghost_height.setSuffix(" px")
        self._ghost_height.setStyleSheet(_INPUT_STYLE)

        self._skin_combo = QComboBox(self)
        self._skin_combo.setStyleSheet(_INPUT_STYLE)

        gh_label = QLabel("Ghost height", self)
        gh_label.setStyleSheet(_LABEL_STYLE)
        skin_label = QLabel("Skin", self)
        skin_label.setStyleSheet(_LABEL_STYLE)

        app_form.addRow(gh_label, self._ghost_height)
        app_form.addRow(skin_label, self._skin_combo)
        root.addLayout(app_form)

        # --- Section: Behaviour ---
        beh_section = QLabel("BEHAVIOUR", self)
        beh_section.setStyleSheet(_SECTION_STYLE)
        root.addWidget(beh_section)

        beh_form = QFormLayout()
        beh_form.setContentsMargins(0, 0, 0, 0)
        beh_form.setSpacing(6)
        beh_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._bubble_timeout = QSpinBox(self)
        self._bubble_timeout.setRange(1, 300)
        self._bubble_timeout.setSuffix(" s")
        self._bubble_timeout.setStyleSheet(_INPUT_STYLE)

        self._idle_interval = QSpinBox(self)
        self._idle_interval.setRange(5, 300)
        self._idle_interval.setSuffix(" s")
        self._idle_interval.setStyleSheet(_INPUT_STYLE)

        bt_label = QLabel("Bubble timeout", self)
        bt_label.setStyleSheet(_LABEL_STYLE)
        ii_label = QLabel("Idle interval", self)
        ii_label.setStyleSheet(_LABEL_STYLE)

        beh_form.addRow(bt_label, self._bubble_timeout)
        beh_form.addRow(ii_label, self._idle_interval)
        root.addLayout(beh_form)

        # --- Action buttons ---
        root.addSpacing(4)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self._cancel_btn = QPushButton("Cancel", self)
        self._cancel_btn.setStyleSheet(_CANCEL_BTN_STYLE)
        self._cancel_btn.clicked.connect(self.hide_settings)

        self._save_btn = QPushButton("Save", self)
        self._save_btn.setStyleSheet(_SAVE_BTN_STYLE)
        self._save_btn.clicked.connect(self._on_save)

        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._save_btn)
        root.addLayout(btn_row)

    def _on_save(self) -> None:
        updated = {
            "gateway_url": self._gateway_url.text().strip(),
            "gateway_token": self._gateway_token.text(),
            "bubble_timeout_ms": self._bubble_timeout.value() * 1000,
            "ghost_height_pixels": self._ghost_height.value(),
            "idle_interval_seconds": float(self._idle_interval.value()),
            "current_skin_id": self._skin_combo.currentText(),
        }
        logger.info("Settings saved: gateway_url=%s", updated["gateway_url"])
        self.settings_saved.emit(updated)
        self.hide_settings()
