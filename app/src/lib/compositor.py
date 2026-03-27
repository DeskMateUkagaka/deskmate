"""Platform-agnostic compositor abstraction for window positioning.

On Wayland compositors (Sway, Hyprland), Qt's QWidget.pos()/move() are no-ops —
the compositor controls window positions. This module provides get/set position
via compositor-specific IPC (swaymsg, hyprctl, xdotool).

Each platform implements get_window_position() and set_window_position().
Returns None / False when the operation isn't supported or fails.
"""

import json
import os
import subprocess

from loguru import logger


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


def get_window_position(*, title: str) -> tuple[float, float] | None:
    """Query the compositor for a window's (x, y) position. Returns None if unsupported."""
    comp = compositor()
    if comp == "sway":
        pos = _sway_get_position(title)
        logger.info(f"get_window_position(title={title}): compositor={comp} pos={pos}")
        return pos
    # Future: hyprland, x11, etc.
    logger.info(f"get_window_position(title={title}): compositor={comp} (unsupported)")
    return None


def _sway_get_position(title: str) -> tuple[float, float] | None:
    try:
        result = subprocess.run(
            ["swaymsg", "-t", "get_tree"],
            capture_output=True,
            timeout=2,
        )
        if result.returncode != 0:
            return None
        tree = json.loads(result.stdout)
        node = _sway_find_node_by_title(tree, title)
        if node and "rect" in node:
            r = node["rect"]
            return float(r["x"]), float(r["y"])
    except Exception as e:
        logger.warning(f"swaymsg get_tree failed: {e}")
    return None


def _sway_find_node_by_title(node: dict, title: str) -> dict | None:
    if node.get("name", "") == title:
        return node
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        found = _sway_find_node_by_title(child, title)
        if found:
            return found
    return None


# ---------------------------------------------------------------------------
# Set window position
# ---------------------------------------------------------------------------


def set_window_position(*, title: str, x: int, y: int) -> bool:
    """Tell the compositor to move a window. Returns True on success."""
    comp = compositor()
    logger.info(f"set_window_position(title={title}, x={x}, y={y}): compositor={comp}")
    if comp == "sway":
        ok = _sway_set_position(title, x, y)
        logger.info(f"set_window_position result: {ok}")
        return ok
    # Future: hyprland, x11, etc.
    return False


def _sway_set_position(title: str, x: int, y: int) -> bool:
    try:
        # 'move absolute position' uses global coordinates matching get_tree's rect
        result = subprocess.run(
            f"swaymsg '[title=\"^{title}$\"] move absolute position {x} {y}'",
            shell=True,
            capture_output=True,
            timeout=2,
        )
        if result.returncode == 0:
            return True
        logger.warning(f"swaymsg move failed: {result.stderr.decode().strip()}")
    except Exception as e:
        logger.warning(f"swaymsg move failed: {e}")
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
            logger.warning(f"swaymsg show failed: {result.stderr.decode().strip()}")
    elif comp == "x11":
        result = subprocess.run(
            ["xdotool", "search", "--name", title, "windowmap"],
            capture_output=True,
        )
        if result.returncode != 0:
            logger.warning(f"xdotool windowmap failed: {result.stderr.decode().strip()}")


def hide_window(*, title: str) -> None:
    """Hide a window by title."""
    comp = compositor()
    if comp == "sway":
        criteria = f'[title="^{title}$"]'
        cmd = f"swaymsg '{criteria} move position 0 -9999'"
        result = subprocess.run(cmd, shell=True, capture_output=True)
        if result.returncode != 0:
            logger.warning(f"swaymsg hide failed: {result.stderr.decode().strip()}")
    elif comp == "x11":
        result = subprocess.run(
            ["xdotool", "search", "--name", title, "windowunmap"],
            capture_output=True,
        )
        if result.returncode != 0:
            logger.warning(f"xdotool windowunmap failed: {result.stderr.decode().strip()}")
