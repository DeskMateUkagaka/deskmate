"""Quake-style dropdown terminal manager for DeskMate.

Uses an embedded TerminalWindow (xterm.js + pty) on Unix, and delegates to
Windows Terminal's built-in quake mode (``wt -w _quake``) on Windows.
Toggle via tray menu or SIGUSR1 signal (Unix).

Usage (Sway config):
    bindsym Ctrl+Alt+grave exec pkill -USR1 -x python3
"""

import shutil
import signal
import subprocess
import sys
import threading

from loguru import logger
from PySide6.QtCore import QAbstractNativeEventFilter, QObject, QTimer, Signal

from src.lib.settings import SettingsManager

if sys.platform != "win32":
    from src.windows.terminal import TerminalWindow

_IS_WIN32 = sys.platform == "win32"


class QuakeTerminalManager(QObject):
    """Manages an embedded terminal window as a quake-style dropdown."""

    toggled = Signal(bool)  # emits visibility state after toggle
    toggle_requested = Signal()  # emitted when SIGUSR1 fires

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._window = None
        self._visible: bool = False
        self._signal_event = threading.Event()
        self._wt_hwnd: int | None = None  # Windows: tracked quake HWND

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setup_signal_handler(self) -> None:
        """Register platform toggle mechanism.

        Unix: SIGUSR1 signal (``pkill -USR1 -x python3``).
        Windows: global Ctrl+` hotkey via RegisterHotKey.
        """
        if _IS_WIN32:
            self._setup_global_hotkey()
            return

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
        if _IS_WIN32:
            return self._wt_toggle()

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
        """Tear down the terminal on program exit."""
        if _IS_WIN32:
            self._wt_close()
            return
        # QWebEngineView cannot be deleted synchronously — Chromium crashes
        # (SIGTRAP) if the widget is freed while the render process is still
        # running.  Hide first, clean up the pty, then schedule deferred deletion.
        if self._window is not None:
            self._window.hide()
            self._window.cleanup()
            self._window.deleteLater()
            self._window = None
        self._visible = False

    def is_running(self) -> bool:
        """Return True if the terminal window exists and pty is alive."""
        if _IS_WIN32:
            return self._wt_hwnd is not None and _win32_is_window(self._wt_hwnd)
        return self._window is not None and self._window.is_running()

    # ------------------------------------------------------------------
    # Internal — toggle signal polling
    # ------------------------------------------------------------------

    def _check_signal(self) -> None:
        if self._signal_event.is_set():
            self._signal_event.clear()
            self.toggle_requested.emit()

    def _setup_global_hotkey(self) -> None:
        """Register Ctrl+` as a system-wide hotkey on Windows."""
        import ctypes

        from PySide6.QtWidgets import QApplication

        user32 = ctypes.windll.user32
        MOD_CONTROL, VK_OEM_3 = 0x0002, 0xC0  # Ctrl, `/~ key
        self._hotkey_id = 0xDECA  # arbitrary unique ID

        if not user32.RegisterHotKey(None, self._hotkey_id, MOD_CONTROL, VK_OEM_3):
            logger.warning("Failed to register global Ctrl+` hotkey (already in use?)")
            return

        logger.info("Global Ctrl+` hotkey registered for quake terminal toggle")

        # Install or reuse the shared native event filter
        app = QApplication.instance()
        self._hotkey_filter = getattr(app, "_win_hotkey_filter", None)
        if self._hotkey_filter is None:
            self._hotkey_filter = WinGlobalHotkeyFilter()
            app._win_hotkey_filter = self._hotkey_filter
            app.installNativeEventFilter(self._hotkey_filter)
        self._hotkey_filter.add(self._hotkey_id, self.toggle_requested)

    # ------------------------------------------------------------------
    # Internal — Windows Terminal quake mode
    #
    # ``wt -w _quake`` always shows/creates the quake window — it never
    # hides it.  We use it only once to spawn, then capture the HWND via
    # GetForegroundWindow (WT focuses the quake window on creation) and
    # toggle visibility ourselves with ShowWindow.
    # ------------------------------------------------------------------

    def _wt_toggle(self) -> bool:
        """Toggle Windows Terminal quake window."""
        import ctypes

        user32 = ctypes.windll.user32
        SW_HIDE, SW_SHOW = 0, 5

        if self._wt_hwnd and user32.IsWindow(self._wt_hwnd):
            if user32.IsWindowVisible(self._wt_hwnd):
                user32.ShowWindow(self._wt_hwnd, SW_HIDE)
                logger.info(f"Quake terminal hidden (hwnd={self._wt_hwnd:#x})")
                return False
            else:
                user32.ShowWindow(self._wt_hwnd, SW_SHOW)
                user32.SetForegroundWindow(self._wt_hwnd)
                logger.info(f"Quake terminal shown (hwnd={self._wt_hwnd:#x})")
                return True

        self._wt_hwnd = None
        return self._wt_spawn()

    def _wt_spawn(self) -> bool:
        """Spawn ``wt -w _quake <command>`` and capture its HWND."""
        wt = _find_wt_exe()
        if wt is None:
            logger.warning("Windows Terminal (wt.exe) not found")
            return False

        cmd = [wt, "-w", "_quake"]
        command = SettingsManager().settings.quake_terminal.command
        if command:
            cmd.extend(command.split())
        try:
            subprocess.Popen(cmd)
            logger.info(f"Quake terminal spawned: {cmd}")
        except OSError as e:
            logger.warning(f"Failed to spawn quake terminal: {e}")
            return False

        # WT focuses the quake window after creation.  Poll
        # GetForegroundWindow until it's a WT window.
        def _capture():
            import ctypes
            import time
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            for _ in range(30):  # up to ~3s
                time.sleep(0.1)
                fg = user32.GetForegroundWindow()
                if not fg:
                    continue
                buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(fg, buf, 256)
                if buf.value == "CASCADIA_HOSTING_WINDOW_CLASS":
                    self._wt_hwnd = fg
                    logger.info(f"Quake terminal HWND captured: {fg:#x}")
                    return
            logger.warning("Could not capture quake terminal HWND")

        threading.Thread(target=_capture, daemon=True, name="wt-capture").start()
        return True

    def _wt_close(self) -> None:
        """Close the quake window and unregister global hotkey on program exit."""
        if hasattr(self, "_hotkey_id"):
            import ctypes

            from PySide6.QtWidgets import QApplication

            if hasattr(self, "_hotkey_filter"):
                QApplication.instance().removeNativeEventFilter(self._hotkey_filter)
            ctypes.windll.user32.UnregisterHotKey(None, self._hotkey_id)
            logger.debug("Global Ctrl+` hotkey unregistered")
        if self._wt_hwnd is None:
            return
        if _win32_is_window(self._wt_hwnd):
            import ctypes

            ctypes.windll.user32.PostMessageW(self._wt_hwnd, 0x0010, 0, 0)  # WM_CLOSE
            logger.info(f"Quake terminal closed (hwnd={self._wt_hwnd:#x})")
        self._wt_hwnd = None

    # ------------------------------------------------------------------
    # Internal — embedded terminal (Unix)
    # ------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# Win32 helpers
# ----------------------------------------------------------------------


class WinGlobalHotkeyFilter(QAbstractNativeEventFilter):
    """Intercept WM_HOTKEY before Qt's event loop consumes it.

    Supports multiple hotkeys.  Call :meth:`add` after ``RegisterHotKey``.
    """

    def __init__(self):
        super().__init__()
        self._handlers: dict[int, Signal] = {}  # hotkey_id → signal

    def add(self, hotkey_id: int, signal: Signal) -> None:
        self._handlers[hotkey_id] = signal

    def nativeEventFilter(self, event_type, message):
        if event_type != b"windows_generic_MSG":
            return False, 0
        import ctypes
        from ctypes import wintypes

        msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
        WM_HOTKEY = 0x0312
        if msg.message == WM_HOTKEY:
            sig = self._handlers.get(msg.wParam)
            if sig is not None:
                sig.emit()
                return True, 0
        return False, 0


def _find_wt_exe() -> str | None:
    """Locate wt.exe — check app execution alias first, then PATH."""
    import os
    from pathlib import Path

    alias = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "wt.exe"
    if alias.exists():
        return str(alias)
    return shutil.which("wt")


def _win32_is_window(hwnd: int) -> bool:
    import ctypes

    return bool(ctypes.windll.user32.IsWindow(hwnd))
