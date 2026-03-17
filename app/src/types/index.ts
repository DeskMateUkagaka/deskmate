export type Expression =
  | 'happy'
  | 'sad'
  | 'angry'
  | 'disgusted'
  | 'condescending'
  | 'thinking'
  | 'neutral'

export const ALL_EXPRESSIONS: Expression[] = [
  'happy',
  'sad',
  'angry',
  'disgusted',
  'condescending',
  'thinking',
  'neutral',
]

export interface GhostPosition {
  x: number
  y: number
}

export type PlacementOrigin = 'center' | 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'

export interface UiPlacement {
  x: number
  y: number
  margin_x: number
  margin_y: number
  origin: PlacementOrigin
}

export interface BubbleTheme {
  background_color: string | null
  border_color: string | null
  border_width: string | null
  border_radius: string | null
  text_color: string | null
  accent_color: string | null
  code_background: string | null
  code_text_color: string | null
  font_family: string | null
  font_size: string | null
  max_bubble_width: number | null
  max_bubble_height: number | null
}

export interface SkinInfo {
  id: string
  name: string
  author: string | null
  version: string | null
  path: string
  bubble_placement: UiPlacement | null
  input_placement: UiPlacement | null
  bubble_theme: BubbleTheme | null
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
