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
