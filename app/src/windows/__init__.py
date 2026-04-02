"""DeskMate UI windows — PySide6 transparent window components."""

import sys

from .bubble import BubbleWindow
from .chat_input import ChatInputWindow
from .get_skins import GetSkinsWindow
from .ghost import GhostWindow
from .settings import SettingsWindow
from .skin_picker import SkinPickerWindow

__all__ = [
    "GhostWindow",
    "BubbleWindow",
    "ChatInputWindow",
    "SettingsWindow",
    "SkinPickerWindow",
    "GetSkinsWindow",
]

if sys.platform == "darwin":
    from .terminal import TerminalWindow

    __all__.append("TerminalWindow")
