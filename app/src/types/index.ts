export type Expression =
  | 'happy'
  | 'sad'
  | 'angry'
  | 'disgusted'
  | 'condescending'
  | 'thinking'
  | 'uwamezukai'
  | 'neutral'

export const ALL_EXPRESSIONS: Expression[] = [
  'happy',
  'sad',
  'angry',
  'disgusted',
  'condescending',
  'thinking',
  'uwamezukai',
  'neutral',
]

export interface GhostPosition {
  x: number
  y: number
}

export interface UiPlacement {
  x: number
  y: number
  margin_x: number
  margin_y: number
}

export interface SkinInfo {
  id: string
  name: string
  author: string | null
  version: string | null
  path: string
  bubble_placement: UiPlacement | null
  input_placement: UiPlacement | null
}

export interface Settings {
  gateway_url: string
  gateway_token: string
  bubble_timeout_ms: number
  proactive_enabled: boolean
  proactive_interval_mins: number
  ghost_x: number
  ghost_y: number
  current_skin_id: string
  ghost_height_pixels: number
}
