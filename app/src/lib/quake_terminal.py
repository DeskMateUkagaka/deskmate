"""Quake-style dropdown terminal manager for DeskMate.

Uses an embedded TerminalWindow (xterm.js + pty) instead of external terminal
emulators. Toggle via tray menu or SIGUSR1 signal.

Usage (Sway config):
    bindsym Ctrl+Alt+grave exec pkill -USR1 -x python3
"""

import signal
import threading

from loguru import logger
from PySide6.QtCore import QObject, QTimer, Signal

from src.windows.terminal import TerminalWindow


class QuakeTerminalManager(QObject):
    """Manages an embedded terminal window as a quake-style dropdown."""

    toggled = Signal(bool)  # emits visibility state after toggle
    toggle_requested = Signal()  # emitted when SIGUSR1 fires

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._window: TerminalWindow | None = None
        self._visible: bool = False
        self._signal_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setup_signal_handler(self) -> None:
        """Register SIGUSR1 and start a QTimer to poll it on the main thread."""
        if not hasattr(signal, "SIGUSR1"):
            logger.info("SIGUSR1 not available on this platform, skipping signal handler")
            return

        def _handler(signum, frame):
            self._signal_event.set()

        signal.signal(signal.SIGUSR1, _handler)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(100)
        self._poll_timer.timeout.connect(self._check_signal)
        self._poll_timer.start()
        logger.info("SIGUSR1 handler registered (pkill -USR1 -x python3 to toggle)")

    def toggle(self, config, screen_rect: tuple[int, int, int, int] | None = None) -> bool:
        """Toggle the terminal. Returns new visibility state.

        screen_rect: (x, y, w, h) of the screen to place the terminal on.
        """
        if self._window is None:
            self._spawn(config, screen_rect)
            return True

        if self._visible:
            self._hide()
            return False
        else:
            self._show(config, screen_rect)
            return True

    def cleanup(self) -> None:
        """Kill the pty and destroy the terminal window.

        The QWebEngineView cannot be deleted synchronously — Chromium crashes
        (SIGTRAP) if the widget is freed while the render process is still
        running. Hide first, clean up the pty, then schedule deferred deletion.
        """
        if self._window is not None:
            self._window.hide()
            self._window.cleanup()
            self._window.deleteLater()
            self._window = None
        self._visible = False

    def is_running(self) -> bool:
        """Return True if the terminal window exists and pty is alive."""
        return self._window is not None and self._window.is_running()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_signal(self) -> None:
        if self._signal_event.is_set():
            self._signal_event.clear()
            self.toggle_requested.emit()

    def _compute_geometry(
        self, config, screen_rect: tuple[int, int, int, int] | None = None
    ) -> tuple[int, int, int, int]:
        """Return (x, y, width, height) for the terminal."""
        if screen_rect:
            sx, sy, sw, sh = screen_rect
        else:
            from PySide6.QtWidgets import QApplication

            screen = QApplication.primaryScreen()
            if screen is None:
                return 0, 0, 1280, 400
            geom = screen.availableGeometry()
            sx, sy, sw, sh = geom.left(), geom.top(), geom.width(), geom.height()

        width = sw
        height = int(sh * config.height_percent / 100)
        return sx, sy, width, height

    def _spawn(self, config, screen_rect=None) -> None:
        """Create the terminal window, position it, spawn pty."""
        x, y, width, height = self._compute_geometry(config, screen_rect)

        self._window = TerminalWindow()
        self._window.terminal_toggle_requested.connect(self.toggle_requested)
        self._window.setGeometry(x, y, width, height)
        self._window.show()
        self._window.spawn(config.command if config.command else None)

        self._visible = True
        self.toggled.emit(True)
        logger.info(f"Quake terminal spawned at ({x},{y},{width},{height})")

    def _show(self, config, screen_rect=None) -> None:
        """Show and reposition the terminal window."""
        if self._window is None:
            return
        x, y, width, height = self._compute_geometry(config, screen_rect)
        self._window.setGeometry(x, y, width, height)
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

        # Respawn pty if the previous command exited
        if not self._window.is_running():
            self._window.spawn(config.command if config.command else None)

        self._visible = True
        self.toggled.emit(True)

    def _hide(self) -> None:
        """Hide the terminal window."""
        if self._window is None:
            return
        self._window.hide()
        self._visible = False
        self.toggled.emit(False)
