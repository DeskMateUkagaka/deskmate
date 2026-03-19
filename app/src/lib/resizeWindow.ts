import { LogicalSize } from '@tauri-apps/api/window'
import type { Window } from '@tauri-apps/api/window'

/**
 * GTK enforces a minimum window size. Windows requested smaller than this
 * will be clamped by the compositor. Position calculations must use the
 * actual size returned by this function, not the requested size.
 */
export const PLATFORM_MIN_WINDOW_HEIGHT = 200

export interface WindowSize {
  width: number
  height: number
}

/**
 * Resize a window and return the actual size after the compositor processes it.
 * GTK may clamp the size to its minimum — the returned size reflects what the
 * compositor actually applied, not what was requested.
 *
 * @param win - Tauri window handle
 * @param width - Desired width in logical pixels
 * @param height - Desired height in logical pixels
 * @returns Actual window size in logical pixels after compositor processing
 */
export async function resizeWindow(win: Window, width: number, height: number): Promise<WindowSize> {
  if (height < PLATFORM_MIN_WINDOW_HEIGHT) {
    console.warn(
      `[resizeWindow] requested height ${height}px is below platform minimum ${PLATFORM_MIN_WINDOW_HEIGHT}px — compositor will clamp`
    )
  }

  await win.setSize(new LogicalSize(width, height))
  // Wait for compositor to process the resize
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))

  const actual = await win.outerSize()
  const scale = await win.scaleFactor()
  return {
    width: actual.width / scale,
    height: actual.height / scale,
  }
}
