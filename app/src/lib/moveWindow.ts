import { invoke } from '@tauri-apps/api/core'
import { LogicalPosition, PhysicalPosition } from '@tauri-apps/api/window'
import type { Window } from '@tauri-apps/api/window'

/**
 * Move a window to (x, y) using compositor-specific positioning (e.g. swaymsg)
 * with fallback to Tauri's built-in setPosition.
 *
 * @param win - Tauri window handle
 * @param x - X coordinate in logical pixels
 * @param y - Y coordinate in logical pixels
 */
export async function moveWindow(win: Window, x: number, y: number): Promise<void> {
  const handled = await invoke<boolean>('move_window', {
    title: win.label ? await getWindowTitle(win) : '',
    x: Math.round(x),
    y: Math.round(y),
  })
  if (!handled) {
    await win.setPosition(new LogicalPosition(x, y))
  }
}

/**
 * Move a window using physical pixel coordinates.
 * For compositor positioning, converts to logical using devicePixelRatio.
 */
export async function moveWindowPhysical(win: Window, x: number, y: number): Promise<void> {
  const logicalX = Math.round(x / window.devicePixelRatio)
  const logicalY = Math.round(y / window.devicePixelRatio)
  const handled = await invoke<boolean>('move_window', {
    title: await getWindowTitle(win),
    x: logicalX,
    y: logicalY,
  })
  if (!handled) {
    await win.setPosition(new PhysicalPosition(x, y))
  }
}

/**
 * Restore a window to a position previously obtained from getWindowPosition().
 * On compositor IPC: passes coords directly (same coordinate space as get_tree).
 * On non-compositor: uses PhysicalPosition (same space as outerPosition).
 */
export async function restoreWindowPosition(win: Window, x: number, y: number): Promise<void> {
  const handled = await invoke<boolean>('move_window', {
    title: await getWindowTitle(win),
    x: Math.round(x),
    y: Math.round(y),
  })
  if (!handled) {
    await win.setPosition(new PhysicalPosition(x, y))
  }
}

/**
 * Get a window's position using compositor IPC (e.g. sway get_tree).
 * Falls back to Tauri's outerPosition() on unsupported compositors.
 * Coordinates are in compositor layout coords (Sway) or physical pixels (fallback).
 * Use restoreWindowPosition() to move back to a saved position.
 */
export async function getWindowPosition(win: Window): Promise<{ x: number; y: number }> {
  const title = await getWindowTitle(win)
  const pos = await invoke<[number, number] | null>('get_window_position', { title })
  if (pos) {
    return { x: pos[0], y: pos[1] }
  }
  const outer = await win.outerPosition()
  return { x: outer.x, y: outer.y }
}

/**
 * Show a hidden window at (x, y), handling compositor differences:
 * - Sway/Wayland: must show() first (hidden windows aren't in compositor tree)
 * - X11/fallback: moveWindow first, then show() (avoids visible flash)
 */
export async function showWindowAt(win: Window, x: number, y: number): Promise<void> {
  const compositorIpc = await invoke<boolean>('uses_compositor_ipc')
  if (compositorIpc) {
    await win.show()
    await moveWindow(win, x, y)
  } else {
    await moveWindow(win, x, y)
    await win.show()
  }
}

// Window title map matching tauri.conf.json
const WINDOW_TITLES: Record<string, string> = {
  'main': 'ukagaka-ghost',
  'settings': 'ukagaka-settings',
  'chat-input': 'ukagaka-input',
  'bubble': 'ukagaka-bubble',
  'skin-picker': 'ukagaka-skin-picker',
}

async function getWindowTitle(win: Window): Promise<string> {
  return WINDOW_TITLES[win.label] ?? win.label
}
