import type { ImageBounds } from '../components/Ghost'

export type Origin =
  | 'center'
  | 'top-left' | 'top-center' | 'top-right'
  | 'bottom-left' | 'bottom-center' | 'bottom-right'

export interface ScreenMargins {
  top: number
  bottom: number
  left: number
  right: number
}

export interface WindowPosition {
  screenX: number
  screenY: number
  /** How far clamping shifted from the ideal position (idealX - screenX) */
  offsetX: number
  /** How far clamping shifted from the ideal position (idealY - screenY) */
  offsetY: number
}

/**
 * Compute anchor point from ghost position + image bounds + skin placement offset.
 * Placement x/y are in original PNG pixel coordinates and get scaled by imageBounds.scale.
 */
export function calcAnchor(
  ghostPos: { x: number; y: number },
  imageBounds: ImageBounds | null,
  placement: { x: number; y: number },
): { x: number; y: number } {
  const s = imageBounds?.scale ?? 1
  const px = placement.x * s
  const py = placement.y * s
  if (imageBounds) {
    return {
      x: ghostPos.x + imageBounds.centerX + px,
      y: ghostPos.y + imageBounds.centerY + py,
    }
  }
  return { x: ghostPos.x + px, y: ghostPos.y + py }
}

/**
 * Compute a clamped screen position for a window.
 *
 * @param targetX - Anchor X in screen coordinates (the point the origin refers to)
 * @param targetY - Anchor Y in screen coordinates
 * @param width - Window width in logical pixels
 * @param height - Window height in logical pixels
 * @param origin - Which point of the window the anchor refers to
 * @param screenWidth - Total screen width
 * @param screenHeight - Total screen height
 * @param margins - Screen edge margins for clamping
 */
export function calcWindowPosition(
  targetX: number,
  targetY: number,
  width: number,
  height: number,
  origin: Origin,
  screenWidth: number,
  screenHeight: number,
  margins: ScreenMargins,
): WindowPosition {
  let idealX: number
  let idealY: number

  switch (origin) {
    case 'top-left':
      idealX = targetX
      idealY = targetY
      break
    case 'top-center':
      idealX = targetX - width / 2
      idealY = targetY
      break
    case 'top-right':
      idealX = targetX - width
      idealY = targetY
      break
    case 'bottom-left':
      idealX = targetX
      idealY = targetY - height
      break
    case 'bottom-center':
      idealX = targetX - width / 2
      idealY = targetY - height
      break
    case 'bottom-right':
      idealX = targetX - width
      idealY = targetY - height
      break
    case 'center':
    default:
      idealX = targetX - width / 2
      idealY = targetY - height / 2
      break
  }

  const screenX = Math.max(margins.left, Math.min(idealX, screenWidth - width - margins.right))
  const screenY = Math.max(margins.top, Math.min(idealY, screenHeight - height - margins.bottom))

  return {
    screenX,
    screenY,
    offsetX: idealX - screenX,
    offsetY: idealY - screenY,
  }
}
