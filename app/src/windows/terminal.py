"""TerminalWindow — embedded terminal using xterm.js in QWebEngineView + pty.

Requires Unix (macOS / Linux) for pty.fork(). On Windows, spawn() is a no-op.
"""

import base64
import json
import os
import shlex
import struct
import sys
import threading

if sys.platform != "win32":
    import fcntl
    import pty
    import select
    import termios

from loguru import logger
from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.lib.compositor import prevent_hide_on_deactivate, remove_dwm_border

# ---------------------------------------------------------------------------
# xterm.js HTML — loaded from CDN on first use, cached by Chromium
# ---------------------------------------------------------------------------

TERMINAL_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/css/xterm.min.css">
<script src="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/lib/xterm.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@xterm/addon-fit@0.10.0/lib/addon-fit.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@xterm/addon-web-links@0.11.0/lib/addon-web-links.min.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<style>
  html, body { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: #1a1a2e; }
  #terminal { width: 100%; height: 100%; }
</style>
</head>
<body>
<div id="terminal"></div>
<script>
let bridge = null;
let term = null;
let fitAddon = null;

function initTerminal() {
    term = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Menlo', monospace",
        theme: {
            background: '#1a1a2e',
            foreground: '#e0e0e0',
            cursor: '#e0e0e0',
            selectionBackground: 'rgba(255, 255, 255, 0.25)',
            black: '#1a1a2e',
            red: '#ff6b6b',
            green: '#51cf66',
            yellow: '#ffd43b',
            blue: '#748ffc',
            magenta: '#da77f2',
            cyan: '#66d9e8',
            white: '#e0e0e0',
            brightBlack: '#495057',
            brightRed: '#ff8787',
            brightGreen: '#69db7c',
            brightYellow: '#ffe066',
            brightBlue: '#91a7ff',
            brightMagenta: '#e599f7',
            brightCyan: '#99e9f2',
            brightWhite: '#f8f9fa',
        },
    });

    fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.loadAddon(new WebLinksAddon.WebLinksAddon());

    term.open(document.getElementById('terminal'));
    fitAddon.fit();

    // Send user input to Python
    term.onData(function(data) {
        if (bridge) bridge.onInput(data);
    });

    // Handle resize
    term.onResize(function(size) {
        if (bridge) bridge.onResize(JSON.stringify({cols: size.cols, rows: size.rows}));
    });

    // Copy on select
    term.onSelectionChange(function() {
        var sel = term.getSelection();
        if (sel) navigator.clipboard.writeText(sel);
    });

    new ResizeObserver(function() {
        if (fitAddon) fitAddon.fit();
    }).observe(document.getElementById('terminal'));
}

new QWebChannel(qt.webChannelTransport, function(channel) {
    bridge = channel.objects.termBridge;
    initTerminal();
    bridge.ready();
});

function writeBase64(b64) {
    if (!term) return;
    var bin = atob(b64);
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    term.write(bytes);
}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# QWebChannel Bridge
# ---------------------------------------------------------------------------


class _TerminalBridge(QObject):
    """JS ↔ Python bridge for terminal I/O."""

    input_received = Signal(str)  # user typed data from xterm.js
    resize_requested = Signal(int, int)  # cols, rows
    js_ready = Signal()

    @Slot(str)
    def onInput(self, data: str) -> None:
        self.input_received.emit(data)

    @Slot(str)
    def onResize(self, payload: str) -> None:
        d = json.loads(payload)
        self.resize_requested.emit(int(d["cols"]), int(d["rows"]))

    @Slot()
    def ready(self) -> None:
        self.js_ready.emit()


# ---------------------------------------------------------------------------
# Pty reader thread
# ---------------------------------------------------------------------------


class _PtyReader(threading.Thread):
    """Background thread that reads from the pty master fd and emits data."""

    def __init__(self, fd: int, callback):
        super().__init__(daemon=True, name="pty-reader")
        self._fd = fd
        self._callback = callback
        self._stop = False

    def run(self):
        while not self._stop:
            try:
                r, _, _ = select.select([self._fd], [], [], 0.05)
                if r:
                    data = os.read(self._fd, 65536)
                    if not data:
                        break
                    self._callback(data)
            except OSError:
                break

    def stop(self):
        self._stop = True


# ---------------------------------------------------------------------------
# Terminal page (opaque background)
# ---------------------------------------------------------------------------


class _TerminalPage(QWebEnginePage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundColor(QColor(26, 26, 46))  # match xterm theme


# ---------------------------------------------------------------------------
# TerminalWindow
# ---------------------------------------------------------------------------


class TerminalWindow(QWidget):
    """Embedded terminal window using xterm.js + pty.

    Spawns a pty with the user's shell (or a configured command),
    renders via xterm.js in QWebEngineView, bridges I/O through QWebChannel.
    """

    window_mapped = Signal()
    _pty_data_received = Signal(str)  # base64-encoded pty output, thread-safe

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowTitle("deskmate-quake")
        remove_dwm_border(self)
        prevent_hide_on_deactivate(self)

        self._master_fd: int | None = None
        self._child_pid: int | None = None
        self._reader: _PtyReader | None = None
        self._command: str | None = None
        self._loaded = False

        # WebView
        self._web = QWebEngineView(self)
        self._page = _TerminalPage(self._web)
        self._web.setPage(self._page)
        self._web.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._page.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        self._page.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )

        # QWebChannel bridge
        self._bridge = _TerminalBridge(self)
        self._channel = QWebChannel(self._page)
        self._channel.registerObject("termBridge", self._bridge)
        self._page.setWebChannel(self._channel)

        self._bridge.input_received.connect(self._on_input)
        self._bridge.resize_requested.connect(self._on_resize)
        self._bridge.js_ready.connect(self._on_js_ready)
        self._pty_data_received.connect(self._write_to_xterm)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._web)

        self._page.setHtml(TERMINAL_HTML)
        self._page.loadFinished.connect(self._on_page_loaded)

        # Poll for child process exit
        self._exit_timer = QTimer(self)
        self._exit_timer.setInterval(500)
        self._exit_timer.timeout.connect(self._check_child)

        logger.info("TerminalWindow created (xterm.js renderer)")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def spawn(self, command: str | None = None) -> None:
        """Spawn a pty with the given command (or user's default shell)."""
        if self._master_fd is not None:
            return  # already running

        self._command = command
        if self._loaded:
            self._do_spawn()

    def is_running(self) -> bool:
        return self._master_fd is not None

    def cleanup(self) -> None:
        """Kill the pty process on app exit."""
        self._exit_timer.stop()
        if self._reader:
            self._reader.stop()
            self._reader = None
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None
        if self._child_pid is not None:
            try:
                os.kill(self._child_pid, 9)
                os.waitpid(self._child_pid, os.WNOHANG)
            except (OSError, ChildProcessError):
                pass
            self._child_pid = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_page_loaded(self, ok: bool):
        if ok:
            # Re-apply platform fixes — Chromium init resets window attributes
            remove_dwm_border(self)
            prevent_hide_on_deactivate(self)

    def _on_js_ready(self):
        self._loaded = True
        logger.debug("TerminalWindow: xterm.js ready")
        if self._command is not None or self._master_fd is None:
            self._do_spawn()

    def _do_spawn(self):
        """Actually fork the pty (Unix only)."""
        if self._master_fd is not None:
            return
        if sys.platform == "win32":
            logger.warning("Embedded terminal not supported on Windows")
            return

        env = os.environ.copy()
        env["TERM"] = "xterm-256color"

        cmd = self._command
        if cmd:
            cmd_parts = shlex.split(cmd)
        else:
            shell = os.environ.get("SHELL", "/bin/sh")
            cmd_parts = [shell]

        pid, fd = pty.fork()
        if pid == 0:
            # Child process
            os.execvpe(cmd_parts[0], cmd_parts, env)
        else:
            self._master_fd = fd
            self._child_pid = pid
            self._reader = _PtyReader(fd, self._on_pty_data)
            self._reader.start()
            self._exit_timer.start()
            logger.info(f"Pty spawned: pid={pid}, cmd={cmd_parts}")

    def _on_pty_data(self, data: bytes):
        """Called from reader thread — emit signal to marshal to Qt main thread."""
        encoded = base64.b64encode(data).decode("ascii")
        self._pty_data_received.emit(encoded)

    def _write_to_xterm(self, b64data: str):
        """Write base64-encoded data to xterm.js (must run on main thread)."""
        self._page.runJavaScript(f'writeBase64("{b64data}");')

    def _on_input(self, data: str):
        """User typed in xterm.js — write to pty master."""
        if self._master_fd is not None:
            try:
                os.write(self._master_fd, data.encode("utf-8"))
            except OSError as e:
                logger.warning(f"pty write failed: {e}")

    def _on_resize(self, cols: int, rows: int):
        """xterm.js resized — update pty window size."""
        if self._master_fd is not None and sys.platform != "win32":
            try:
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)
            except OSError as e:
                logger.debug(f"pty resize failed: {e}")

    def _check_child(self):
        """Poll whether the child process has exited."""
        if self._child_pid is None:
            return
        try:
            pid, status = os.waitpid(self._child_pid, os.WNOHANG)
            if pid != 0:
                logger.info(f"Pty child exited (pid={self._child_pid}, status={status})")
                self._cleanup_pty()
        except ChildProcessError:
            self._cleanup_pty()

    def _cleanup_pty(self):
        """Clean up after child exits, but keep the window alive for respawn."""
        if self._reader:
            self._reader.stop()
            self._reader = None
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None
        self._child_pid = None
        self._exit_timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(20, self.window_mapped.emit)

    def closeEvent(self, event):
        # Hide instead of close so we can toggle
        event.ignore()
        self.hide()
