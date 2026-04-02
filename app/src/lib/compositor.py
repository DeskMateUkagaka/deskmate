"""Platform-agnostic compositor abstraction for window positioning.

On Wayland compositors (Sway, Hyprland), Qt's QWidget.pos()/move() are no-ops —
the compositor controls window positions. This module provides a singleton
Compositor with get/set position, show/hide, and window-wait via IPC.

Usage:
    from src.lib.compositor import compositor
    compositor().set_window_position(title="my-win", x=100, y=200)
"""

import abc
import ctypes
import json
import os
import socket
import struct
import subprocess
import sys

from loguru import logger
from PySide6.QtCore import QTimer

# ---------------------------------------------------------------------------
# Sway IPC (direct socket, no subprocess)
# ---------------------------------------------------------------------------

_SWAY_MAGIC = b"i3-ipc"
_SWAY_HEADER = struct.Struct("<6sII")  # magic(6) + length(u32) + type(u32)

# Message types
_IPC_COMMAND = 0
_IPC_GET_TREE = 4
_IPC_GET_OUTPUTS = 3


def _sway_ipc(msg_type: int, payload: str = "") -> dict | list | None:
    """Send a single IPC message to sway and return the parsed JSON response."""
    sock_path = os.environ.get("SWAYSOCK")
    if not sock_path:
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            sock.connect(sock_path)
            data = payload.encode()
            sock.sendall(_SWAY_HEADER.pack(_SWAY_MAGIC, len(data), msg_type) + data)
            # read response header
            hdr = b""
            while len(hdr) < _SWAY_HEADER.size:
                hdr += sock.recv(_SWAY_HEADER.size - len(hdr))
            _, resp_len, _ = _SWAY_HEADER.unpack(hdr)
            # read response body
            body = b""
            while len(body) < resp_len:
                body += sock.recv(resp_len - len(body))
            return json.loads(body)
    except Exception as e:
        logger.warning(f"sway IPC failed: {e}")
        return None


def _sway_command(cmd: str) -> bool:
    """Run a sway command via IPC. Returns True if all results succeeded."""
    result = _sway_ipc(_IPC_COMMAND, cmd)
    if result is None:
        return False
    if isinstance(result, list):
        return all(r.get("success", False) for r in result)
    return result.get("success", False)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class Compositor(abc.ABC):
    """Abstract base for compositor IPC operations."""

    @abc.abstractmethod
    def get_screen_at(self, x: int, y: int) -> tuple[int, int, int, int] | None:
        """Return (x, y, width, height) of the output containing the given point."""

    @abc.abstractmethod
    def get_window_position(self, title: str) -> tuple[float, float] | None:
        """Query for a window's (x, y) position. Returns None if not found."""

    @abc.abstractmethod
    def set_window_position(self, title: str, x: int, y: int) -> bool:
        """Move a window. Returns True on success."""

    @abc.abstractmethod
    def show_window(self, title: str, x: int, y: int, width: int, height: int) -> None:
        """Show and position a window by title."""

    @abc.abstractmethod
    def hide_window(self, title: str) -> None:
        """Hide a window by title."""

    @abc.abstractmethod
    def find_window(self, title: str) -> bool:
        """Return True if a window with the given title exists."""

    def wait_for_window(
        self, title: str, callback, interval_ms: int = 50, timeout_ms: int = 5000
    ) -> None:
        """Poll until a window appears, then call callback. Gives up after timeout."""
        elapsed = 0

        def _poll():
            nonlocal elapsed
            if self.find_window(title):
                timer.stop()
                logger.debug(f"[compositor] window '{title}' appeared after ~{elapsed}ms")
                callback()
                return
            elapsed += interval_ms
            if elapsed >= timeout_ms:
                timer.stop()
                logger.warning(
                    f"[compositor] timed out waiting for window '{title}' after {timeout_ms}ms"
                )

        timer = QTimer()
        timer.setInterval(interval_ms)
        timer.timeout.connect(_poll)
        timer.start()


# ---------------------------------------------------------------------------
# Sway
# ---------------------------------------------------------------------------


class SwayCompositor(Compositor):
    """Sway IPC via direct Unix socket (no subprocess)."""

    def _get_tree(self) -> dict | None:
        return _sway_ipc(_IPC_GET_TREE)

    def _find_node(self, title: str) -> dict | None:
        tree = self._get_tree()
        if not tree:
            return None
        return self._find_node_in(tree, title)

    def _find_node_in(self, node: dict, title: str) -> dict | None:
        if node.get("name", "") == title:
            return node
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            found = self._find_node_in(child, title)
            if found:
                return found
        return None

    def _criteria(self, title: str) -> str:
        return f'[title="^{title}$"]'

    def _cmd(self, cmd: str) -> bool:
        logger.debug(f"[sway] command: {cmd}")
        ok = _sway_command(cmd)
        if not ok:
            logger.warning(f"sway command failed: {cmd}")
        return ok

    # -- Abstract implementations --

    def get_screen_at(self, x: int, y: int) -> tuple[int, int, int, int] | None:
        outputs = _sway_ipc(_IPC_GET_OUTPUTS)
        if not outputs:
            return None
        for out in outputs:
            if not out.get("active"):
                continue
            r = out.get("rect", {})
            ox, oy = r.get("x", 0), r.get("y", 0)
            ow, oh = r.get("width", 0), r.get("height", 0)
            logger.debug(
                f"[sway] output '{out.get('name')}': rect=({ox},{oy},{ow},{oh}) scale={out.get('scale')}"
            )
            if ox <= x < ox + ow and oy <= y < oy + oh:
                logger.debug(
                    f"[sway] point ({x},{y}) -> output '{out.get('name')}' ({ox},{oy},{ow},{oh})"
                )
                return (ox, oy, ow, oh)
        return None

    def get_output_name_at(self, x: int, y: int) -> str | None:
        """Return the output name containing the given point."""
        outputs = _sway_ipc(_IPC_GET_OUTPUTS)
        if not outputs:
            return None
        for out in outputs:
            if not out.get("active"):
                continue
            r = out.get("rect", {})
            ox, oy = r.get("x", 0), r.get("y", 0)
            ow, oh = r.get("width", 0), r.get("height", 0)
            if ox <= x < ox + ow and oy <= y < oy + oh:
                return out.get("name")
        return None

    def get_window_position(self, title: str) -> tuple[float, float] | None:
        node = self._find_node(title)
        if node and "rect" in node:
            r = node["rect"]
            pos = (float(r["x"]), float(r["y"]))
            logger.info(f"get_window_position(title={title}): sway pos={pos}")
            return pos
        logger.info(f"get_window_position(title={title}): sway not found")
        return None

    def set_window_position(self, title: str, x: int, y: int) -> bool:
        logger.info(f"set_window_position(title={title}, x={x}, y={y}): sway")
        ok = self._cmd(f"{self._criteria(title)} move absolute position {x} {y}")
        logger.info(f"set_window_position result: {ok}")
        return ok

    def show_window(self, title: str, x: int, y: int, width: int, height: int) -> None:
        logger.debug(f"[sway] show_window: title={title} x={x} y={y} w={width} h={height}")
        c = self._criteria(title)
        # Pull from scratchpad first — may fail if window was never hidden, that's OK.
        _sway_command(f"{c} scratchpad show")
        _sway_command(f"{c} floating enable")
        # move absolute position is unreliable with fractional scaling.
        # Move to the correct output first, then use output-relative coordinates.
        output_name = self.get_output_name_at(x, y)
        screen = self.get_screen_at(x, y) if output_name else None
        if output_name and screen:
            rel_x = x - screen[0]
            rel_y = y - screen[1]
            logger.debug(
                f"[sway] -> output={output_name} rel=({rel_x},{rel_y}) size=({width},{height})"
            )
            _sway_command(f"{c} move to output {output_name}")
            resize_cmd = f"{c} resize set {width} {height}, move position {rel_x} {rel_y}, focus"
        else:
            resize_cmd = f"{c} resize set {width} {height}, move position {x} {y}, focus"
        # Apps (e.g. kitty) may override the resize during initialization.
        # Retry until the size sticks (up to 5 attempts, 100ms apart).
        self._cmd(resize_cmd)
        attempts_left = 5

        def _verify_resize():
            nonlocal attempts_left
            node = self._find_node(title)
            if node:
                r = node.get("rect", {})
                actual_w, actual_h = r.get("width", 0), r.get("height", 0)
                # Allow some tolerance for cell rounding (kitty rounds to char cells)
                if abs(actual_w - width) > 20 or abs(actual_h - height) > 40:
                    attempts_left -= 1
                    logger.debug(
                        f"[sway] resize mismatch: wanted ({width},{height}) "
                        f"got ({actual_w},{actual_h}), retries left={attempts_left}"
                    )
                    if attempts_left > 0:
                        _sway_command(resize_cmd)
                        QTimer.singleShot(100, _verify_resize)
                    return
            logger.debug(f"[sway] resize verified for '{title}'")

        QTimer.singleShot(100, _verify_resize)

    def hide_window(self, title: str) -> None:
        self._cmd(f"{self._criteria(title)} move scratchpad")

    def find_window(self, title: str) -> bool:
        return self._find_node(title) is not None


# ---------------------------------------------------------------------------
# X11
# ---------------------------------------------------------------------------


class X11Compositor(Compositor):
    """X11 via xdotool."""

    def _find_wid(self, title: str) -> str | None:
        result = subprocess.run(["xdotool", "search", "--name", f"^{title}$"], capture_output=True)
        if result.returncode != 0:
            return None
        wids = result.stdout.decode().strip().split("\n")
        return wids[0] if wids and wids[0] else None

    def get_screen_at(self, x: int, y: int) -> tuple[int, int, int, int] | None:
        return None  # not implemented for X11

    def get_window_position(self, title: str) -> tuple[float, float] | None:
        wid = self._find_wid(title)
        if not wid:
            return None
        result = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", wid], capture_output=True
        )
        if result.returncode != 0:
            return None
        vals = {}
        for line in result.stdout.decode().strip().split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                vals[k] = v
        if "X" in vals and "Y" in vals:
            return float(vals["X"]), float(vals["Y"])
        return None

    def set_window_position(self, title: str, x: int, y: int) -> bool:
        wid = self._find_wid(title)
        if not wid:
            return False
        result = subprocess.run(["xdotool", "windowmove", wid, str(x), str(y)], capture_output=True)
        return result.returncode == 0

    def show_window(self, title: str, x: int, y: int, width: int, height: int) -> None:
        wid = self._find_wid(title)
        if not wid:
            logger.warning(f"xdotool: window '{title}' not found")
            return
        result = subprocess.run(
            [
                "xdotool",
                "windowmap",
                "--sync",
                wid,
                "windowmove",
                wid,
                str(x),
                str(y),
                "windowsize",
                wid,
                str(width),
                str(height),
                "windowfocus",
                wid,
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            logger.warning(f"xdotool show failed: {result.stderr.decode().strip()}")

    def hide_window(self, title: str) -> None:
        wid = self._find_wid(title)
        if not wid:
            return
        result = subprocess.run(["xdotool", "windowunmap", wid], capture_output=True)
        if result.returncode != 0:
            logger.warning(f"xdotool hide failed: {result.stderr.decode().strip()}")

    def find_window(self, title: str) -> bool:
        return self._find_wid(title) is not None


# ---------------------------------------------------------------------------
# Null (unsupported)
# ---------------------------------------------------------------------------


class NullCompositor(Compositor):
    """Fallback for unsupported compositors — all operations are no-ops."""

    def get_screen_at(self, x, y):
        return None

    def get_window_position(self, title):
        return None

    def set_window_position(self, title, x, y):
        return False

    def show_window(self, title, x, y, width, height):
        pass

    def hide_window(self, title):
        pass

    def find_window(self, title):
        return False


# ---------------------------------------------------------------------------
# Windows DWM border removal
# ---------------------------------------------------------------------------


def prevent_hide_on_deactivate(widget) -> None:
    """Prevent a Qt Tool window from hiding when the app loses focus on macOS.

    macOS NSPanels (created by Qt for Tool-type windows) hide automatically
    when the application deactivates.  Setting hidesOnDeactivate = NO keeps
    them visible, which is the expected behaviour for a desktop companion.

    Safe to call on non-macOS platforms (no-op).
    """
    if sys.platform != "darwin":
        return
    try:
        from ctypes import c_bool, c_void_p

        objc = ctypes.cdll.LoadLibrary("libobjc.dylib")
        objc.objc_msgSend.restype = c_void_p
        objc.objc_msgSend.argtypes = [c_void_p, c_void_p]

        sel_reg = objc.sel_registerName
        sel_reg.restype = c_void_p
        sel_reg.argtypes = [ctypes.c_char_p]

        # Get NSView from Qt widget, then its NSWindow
        view_ptr = c_void_p(int(widget.winId()))
        window_sel = sel_reg(b"window")
        ns_window = objc.objc_msgSend(view_ptr, window_sel)
        if not ns_window:
            return

        # [nsWindow setHidesOnDeactivate:NO]
        set_hides_sel = sel_reg(b"setHidesOnDeactivate:")
        objc.objc_msgSend.argtypes = [c_void_p, c_void_p, c_bool]
        objc.objc_msgSend(ns_window, set_hides_sel, False)
        objc.objc_msgSend.argtypes = [c_void_p, c_void_p]

        logger.debug("prevent_hide_on_deactivate: applied")
    except Exception as e:
        logger.debug(f"prevent_hide_on_deactivate failed: {e}")


def remove_dwm_border(widget) -> None:
    """Remove the Windows 11 DWM border and rounded corners from a frameless window.

    On Windows 11, the Desktop Window Manager draws a visible rounded border
    around all windows, including frameless transparent ones.  Three DWM
    attributes together suppress it completely:

    1. DWMWA_NCRENDERING_POLICY = DISABLED — stop DWM non-client rendering.
    2. DWMWA_WINDOW_CORNER_PREFERENCE = DONOTROUND — disable rounded corners.
    3. DWMWA_BORDER_COLOR = COLOR_NONE — suppress the border color.

    Safe to call on non-Windows platforms (no-op).
    """
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        dwmapi = ctypes.windll.dwmapi

        # Disable non-client area rendering
        policy = ctypes.c_uint32(1)  # DWMNCRP_DISABLED
        dwmapi.DwmSetWindowAttribute(hwnd, 2, ctypes.byref(policy), ctypes.sizeof(policy))

        # Disable rounded corners
        pref = ctypes.c_uint32(1)  # DWMWCP_DONOTROUND
        dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))

        # Suppress border color
        color = ctypes.c_uint32(0xFFFFFFFE)  # DWMWA_COLOR_NONE
        dwmapi.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(color), ctypes.sizeof(color))

        logger.debug(f"remove_dwm_border: applied to HWND {hwnd:#x}")
    except Exception as e:
        logger.debug(f"remove_dwm_border failed (pre-Win11?): {e}")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Compositor | None = None


def compositor() -> Compositor:
    """Return the singleton Compositor for the current platform."""
    global _instance
    if _instance is not None:
        return _instance

    if os.environ.get("SWAYSOCK"):
        _instance = SwayCompositor()
        logger.info("Compositor: Sway")
    elif os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        # Hyprland could be added as a subclass later
        _instance = NullCompositor()
        logger.info("Compositor: Hyprland (not yet implemented, using null)")
    elif os.environ.get("DISPLAY"):
        _instance = X11Compositor()
        logger.info("Compositor: X11")
    else:
        _instance = NullCompositor()
        logger.info("Compositor: unknown (using null)")

    return _instance
