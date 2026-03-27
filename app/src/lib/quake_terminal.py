"""Quake-style dropdown terminal manager for DeskMate.

Spawns an external terminal emulator and shows/hides it via compositor
commands (Sway, X11 fallback). Toggle is triggered by calling toggle()
directly or via SIGUSR1 signal from an external keybind.

Usage (Sway config):
    bindsym Ctrl+Alt+grave exec pkill -USR1 -x python3
"""

import logging
import os
import platform
import shutil
import signal
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from src.lib.compositor import show_window, hide_window

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Terminal emulator definitions
# ---------------------------------------------------------------------------


def _detect_terminal(override: str | None = None) -> str | None:
    """Return the first available terminal emulator command."""
    if override:
        return override if shutil.which(override) else None

    system = platform.system()

    if system == "Linux":
        candidates = ["foot", "kitty", "alacritty", "konsole", "xterm", "xfce4-terminal"]
        for cmd in candidates:
            if shutil.which(cmd):
                return cmd
        return None

    if system == "Darwin":
        iterm = Path("/Applications/iTerm.app")
        if iterm.exists():
            return "iterm2"
        for cmd in ["kitty", "alacritty"]:
            if shutil.which(cmd):
                return cmd
        return "open -a Terminal"

    if system == "Windows":
        if shutil.which("wt"):
            return "wt"
        if shutil.which("powershell"):
            return "powershell"
        return None

    return None


def _build_spawn_args(
    terminal: str, title: str, width_px: int, height_px: int, command: str
) -> list[str]:
    """Build the argv list for launching the terminal."""
    cols = max(40, width_px // 8)  # rough char width estimate
    rows = max(10, height_px // 16)  # rough char height estimate
    cmd_parts = command.split()

    if terminal == "foot":
        return [
            "foot",
            f"--title={title}",
            f"--window-size-pixels={width_px}x{height_px}",
            "-e",
            *cmd_parts,
        ]

    if terminal == "kitty":
        return [
            "kitty",
            "--title",
            title,
            "-o",
            f"initial_window_width={width_px}",
            "-o",
            f"initial_window_height={height_px}",
            "-e",
            *cmd_parts,
        ]

    if terminal == "alacritty":
        return [
            "alacritty",
            "--title",
            title,
            "-e",
            *cmd_parts,
        ]

    if terminal == "konsole":
        return [
            "konsole",
            "--hide-menubar",
            "--hide-tabbar",
            "-p",
            f"tabtitle={title}",
            "-e",
            *cmd_parts,
        ]

    if terminal == "xterm":
        return [
            "xterm",
            "-T",
            title,
            "-geometry",
            f"{cols}x{rows}",
            "-e",
            *cmd_parts,
        ]

    if terminal in ("xfce4-terminal",):
        return [
            terminal,
            f"--title={title}",
            "-e",
            command,
        ]

    # Generic fallback
    return [terminal, "-e", *cmd_parts]



# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

_WINDOW_TITLE = "deskmate-quake"


class QuakeTerminalManager(QObject):
    """Manages an external terminal process as a quake-style dropdown."""

    toggled = Signal(bool)  # emits visibility state after toggle
    toggle_requested = Signal()  # emitted when SIGUSR1 fires; connect to trigger toggle

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._process: subprocess.Popen | None = None
        self._visible: bool = False
        self._signal_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setup_signal_handler(self) -> None:
        """Register SIGUSR1 and start a QTimer to poll it on the main thread."""

        def _handler(signum, frame):
            self._signal_event.set()

        signal.signal(signal.SIGUSR1, _handler)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(100)
        self._poll_timer.timeout.connect(self._check_signal)
        self._poll_timer.start()
        logger.info("SIGUSR1 handler registered (pkill -USR1 -x python3 to toggle)")

    def toggle(self, config) -> bool:
        """Toggle the terminal. Returns new visibility state."""
        # Check if previously spawned process is still alive
        if self._process is not None and self._process.poll() is not None:
            logger.info(
                "Terminal process exited (returncode=%d), resetting state", self._process.returncode
            )
            self._process = None
            self._visible = False

        if self._process is None:
            return self._spawn(config)

        if self._visible:
            self._hide()
            return False
        else:
            self._show(config)
            return True

    def cleanup(self) -> None:
        """Kill the terminal process on app exit."""
        if self._process is not None and self._process.poll() is None:
            logger.info("Terminating quake terminal process (pid=%d)", self._process.pid)
            self._process.terminate()
            self._process = None
        self._visible = False

    def is_running(self) -> bool:
        """Return True if the terminal process is alive."""
        return self._process is not None and self._process.poll() is None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_signal(self) -> None:
        if self._signal_event.is_set():
            self._signal_event.clear()
            # Config is owned by the caller — emit toggle_requested so the owner
            # calls toggle() with the right config on the main thread.
            self.toggle_requested.emit()

    def _compute_geometry(self, config) -> tuple[int, int, int, int]:
        """Return (x, y, width, height) in screen pixels for the terminal."""
        from PySide6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        if screen is None:
            return 0, 0, 1280, 400

        geom = screen.availableGeometry()
        width = geom.width()
        height = int(geom.height() * config.height_percent / 100)
        return geom.left(), geom.top(), width, height

    def _spawn(self, config) -> bool:
        """Detect terminal, spawn it, position it, return True on success."""
        terminal = _detect_terminal(config.terminal_emulator)
        if terminal is None:
            logger.error("No supported terminal emulator found on PATH")
            return False

        x, y, width, height = self._compute_geometry(config)
        args = _build_spawn_args(terminal, _WINDOW_TITLE, width, height, config.command)

        logger.info("Spawning terminal: %s", " ".join(args))
        self._process = subprocess.Popen(args)
        logger.info("Terminal spawned (pid=%d)", self._process.pid)

        # Give the terminal a moment to create its window before positioning
        QTimer.singleShot(400, lambda: show_window(title=_WINDOW_TITLE, x=x, y=y, width=width, height=height))

        self._visible = True
        self.toggled.emit(True)
        return True

    def _show(self, config) -> None:
        x, y, width, height = self._compute_geometry(config)
        show_window(title=_WINDOW_TITLE, x=x, y=y, width=width, height=height)
        self._visible = True
        self.toggled.emit(True)

    def _hide(self) -> None:
        hide_window(title=_WINDOW_TITLE)
        self._visible = False
        self.toggled.emit(False)
