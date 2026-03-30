"""Unified window positioning: anchor calculation + origin-aware clamping.

Ported from app-tauri/src/lib/windowPosition.ts.
"""

from typing import NamedTuple

Origin = str
# "center", "top-left", "top-center", "top-right",
# "bottom-left", "bottom-center", "bottom-right"


class ScreenMargins(NamedTuple):
    top: int = 0
    bottom: int = 0
    left: int = 0
    right: int = 0


class WindowPosition(NamedTuple):
    screen_x: int
    screen_y: int
    offset_x: int  # how far clamping shifted from ideal (ideal_x - screen_x)
    offset_y: int  # how far clamping shifted from ideal (ideal_y - screen_y)


def calc_anchor(
    ghost_x: int,
    ghost_y: int,
    image_bounds: dict | None,
    placement_x: float = 0,
    placement_y: float = 0,
) -> tuple[int, int]:
    """Compute anchor point from ghost position + image bounds + placement offset.

    image_bounds: dict with centerX/centerY/scale keys (from GhostWindow.image_bounds()).
    placement_x/y: skin-defined offset in **original PNG pixel coordinates** —
    they are scaled by image_bounds["scale"] (targetHeight / naturalHeight).
    """
    s = image_bounds.get("scale", 1.0) if image_bounds else 1.0
    px = int(placement_x * s)
    py = int(placement_y * s)
    if image_bounds:
        return (
            ghost_x + image_bounds["centerX"] + px,
            ghost_y + image_bounds["centerY"] + py,
        )
    return (ghost_x + px, ghost_y + py)


class ScreenRect(NamedTuple):
    x: int = 0
    y: int = 0
    width: int = 1920
    height: int = 1080


def calc_window_position(
    target_x: int,
    target_y: int,
    width: int,
    height: int,
    origin: Origin,
    screen_width: int = 0,
    screen_height: int = 0,
    margins: ScreenMargins = ScreenMargins(),
    screen: ScreenRect | None = None,
) -> WindowPosition:
    """Compute a clamped screen position for a window.

    target_x/y: anchor point in screen coordinates.
    origin: which point of the window the anchor refers to.
    screen: full screen geometry (global coords). If provided, screen_width/height are ignored.
    """
    if screen is None:
        screen = ScreenRect(0, 0, screen_width, screen_height)

    if origin == "top-left":
        ideal_x, ideal_y = target_x, target_y
    elif origin == "top-center":
        ideal_x, ideal_y = target_x - width // 2, target_y
    elif origin == "top-right":
        ideal_x, ideal_y = target_x - width, target_y
    elif origin == "bottom-left":
        ideal_x, ideal_y = target_x, target_y - height
    elif origin == "bottom-center":
        ideal_x, ideal_y = target_x - width // 2, target_y - height
    elif origin == "bottom-right":
        ideal_x, ideal_y = target_x - width, target_y - height
    else:  # "center" or default
        ideal_x, ideal_y = target_x - width // 2, target_y - height // 2

    screen_x = max(screen.x + margins.left, min(ideal_x, screen.x + screen.width - width - margins.right))
    screen_y = max(screen.y + margins.top, min(ideal_y, screen.y + screen.height - height - margins.bottom))

    return WindowPosition(
        screen_x=screen_x,
        screen_y=screen_y,
        offset_x=ideal_x - screen_x,
        offset_y=ideal_y - screen_y,
    )
