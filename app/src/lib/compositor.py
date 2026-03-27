"""Platform-agnostic compositor abstraction for window positioning.

On Wayland compositors (Sway, Hyprland), Qt's QWidget.pos()/move() are no-ops —
the compositor controls window positions. This module provides get/set position
via compositor-specific IPC (swaymsg, hyprctl, xdotool).

Each platform implements get_window_position() and set_window_position().
Returns None / False when the operation isn't supported or fails.
"""

import json
import logging
import os
import subprocess

logger = logging.getLogger(__name__)


def compositor() -> str:
    """Return 'sway', 'hyprland', 'x11', or 'unknown'."""
    if os.environ.get("SWAYSOCK"):
        return "sway"
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "hyprland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


# ---------------------------------------------------------------------------
# Get window position
# ---------------------------------------------------------------------------


def get_window_position(*, app_id: str) -> tuple[float, float] | None:
    """Query the compositor for a window's (x, y) position. Returns None if unsupported."""
    comp = compositor()
    if comp == "sway":
        pos = _sway_get_position(app_id)
        logger.info("get_window_position(%s): compositor=%s pos=%s", app_id, comp, pos)
        return pos
    # Future: hyprland, x11, etc.
    logger.info("get_window_position(%s): compositor=%s (unsupported)", app_id, comp)
    return None


def _sway_get_position(app_id: str) -> tuple[float, float] | None:
    try:
        result = subprocess.run(
            ["swaymsg", "-t", "get_tree"],
            capture_output=True,
            timeout=2,
        )
        if result.returncode != 0:
            return None
        tree = json.loads(result.stdout)
        node = _sway_find_node(tree, app_id)
        if node and "rect" in node:
            r = node["rect"]
            return float(r["x"]), float(r["y"])
    except Exception as e:
        logger.warning("swaymsg get_tree failed: %s", e)
    return None


def _sway_find_node(node: dict, app_id: str) -> dict | None:
    if node.get("app_id", "") == app_id:
        return node
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        found = _sway_find_node(child, app_id)
        if found:
            return found
    return None


# ---------------------------------------------------------------------------
# Set window position
# ---------------------------------------------------------------------------


def set_window_position(*, app_id: str, x: int, y: int) -> bool:
    """Tell the compositor to move a window. Returns True on success."""
    comp = compositor()
    logger.info("set_window_position(%s, x=%d, y=%d): compositor=%s", app_id, x, y, comp)
    if comp == "sway":
        ok = _sway_set_position(app_id, x, y)
        logger.info("set_window_position result: %s", ok)
        return ok
    # Future: hyprland, x11, etc.
    return False


def _sway_set_position(app_id: str, x: int, y: int) -> bool:
    try:
        # 'move absolute position' uses global coordinates matching get_tree's rect
        result = subprocess.run(
            f"swaymsg '[app_id=\"{app_id}\"] move absolute position {x} {y}'",
            shell=True,
            capture_output=True,
            timeout=2,
        )
        if result.returncode == 0:
            return True
        logger.warning("swaymsg move failed: %s", result.stderr.decode().strip())
    except Exception as e:
        logger.warning("swaymsg move failed: %s", e)
    return False


# ---------------------------------------------------------------------------
# Show / hide (used by quake terminal)
# ---------------------------------------------------------------------------


def show_window(*, title: str, x: int, y: int, width: int, height: int) -> None:
    """Show and position a window by title."""
    comp = compositor()
    if comp == "sway":
        criteria = f'[title="^{title}$"]'
        cmd = f"swaymsg '{criteria} move position {x} {y}, resize set {width} {height}, focus'"
        result = subprocess.run(cmd, shell=True, capture_output=True)
        if result.returncode != 0:
            logger.warning("swaymsg show failed: %s", result.stderr.decode().strip())
    elif comp == "x11":
        result = subprocess.run(
            ["xdotool", "search", "--name", title, "windowmap"],
            capture_output=True,
        )
        if result.returncode != 0:
            logger.warning("xdotool windowmap failed: %s", result.stderr.decode().strip())


def hide_window(*, title: str) -> None:
    """Hide a window by title."""
    comp = compositor()
    if comp == "sway":
        criteria = f'[title="^{title}$"]'
        cmd = f"swaymsg '{criteria} move position 0 -9999'"
        result = subprocess.run(cmd, shell=True, capture_output=True)
        if result.returncode != 0:
            logger.warning("swaymsg hide failed: %s", result.stderr.decode().strip())
    elif comp == "x11":
        result = subprocess.run(
            ["xdotool", "search", "--name", title, "windowunmap"],
            capture_output=True,
        )
        if result.returncode != 0:
            logger.warning("xdotool windowunmap failed: %s", result.stderr.decode().strip())
