"""Platform-agnostic compositor abstraction for window positioning.

On Wayland compositors (Sway, Hyprland), Qt's QWidget.pos()/move() are no-ops —
the compositor controls window positions. This module provides a singleton
Compositor with get/set position, show/hide, and window-wait via IPC.

Usage:
    from src.lib.compositor import compositor
    compositor().set_window_position(title="my-win", x=100, y=200)
"""

import abc
import json
import os
import subprocess

from loguru import logger
from PySide6.QtCore import QTimer

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
    """Sway IPC via swaymsg."""

    def _run(self, cmd: str, shell: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, shell=shell, capture_output=True, timeout=2)

    def _get_tree(self) -> dict | None:
        try:
            result = subprocess.run(["swaymsg", "-t", "get_tree"], capture_output=True, timeout=2)
            if result.returncode != 0:
                return None
            return json.loads(result.stdout)
        except Exception as e:
            logger.warning(f"swaymsg get_tree failed: {e}")
            return None

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

    # -- Abstract implementations --

    def get_screen_at(self, x: int, y: int) -> tuple[int, int, int, int] | None:
        try:
            result = subprocess.run(
                ["swaymsg", "-t", "get_outputs"], capture_output=True, timeout=2
            )
            if result.returncode != 0:
                return None
            outputs = json.loads(result.stdout)
            for out in outputs:
                if not out.get("active"):
                    continue
                r = out.get("rect", {})
                ox, oy = r.get("x", 0), r.get("y", 0)
                ow, oh = r.get("width", 0), r.get("height", 0)
                if ox <= x < ox + ow and oy <= y < oy + oh:
                    return (ox, oy, ow, oh)
        except Exception as e:
            logger.warning(f"swaymsg get_outputs failed: {e}")
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
        result = self._run(f"swaymsg '{self._criteria(title)} move absolute position {x} {y}'")
        if result.returncode == 0:
            logger.info("set_window_position result: True")
            return True
        logger.warning(f"swaymsg move failed: {result.stderr.decode().strip()}")
        return False

    def show_window(self, title: str, x: int, y: int, width: int, height: int) -> None:
        c = self._criteria(title)
        # scratchpad show pulls from scratchpad (no-op if not in scratchpad).
        # floating enable is required — the window may be tiled.
        cmd = f"swaymsg '{c} scratchpad show, floating enable, move position {x} {y}, resize set {width} {height}, focus'"
        result = self._run(cmd)
        if result.returncode != 0:
            logger.warning(f"swaymsg show failed: {result.stderr.decode().strip()}")

    def hide_window(self, title: str) -> None:
        result = self._run(f"swaymsg '{self._criteria(title)} move scratchpad'")
        if result.returncode != 0:
            logger.warning(f"swaymsg hide failed: {result.stderr.decode().strip()}")

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
