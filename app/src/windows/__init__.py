"""DeskMate UI windows — PySide6 transparent window components."""

from .bubble import BubbleWindow
from .chat_input import ChatInputWindow
from .ghost import GhostWindow
from .settings import SettingsWindow
from .skin_picker import SkinPickerWindow

__all__ = ["GhostWindow", "BubbleWindow", "ChatInputWindow", "SettingsWindow", "SkinPickerWindow"]
