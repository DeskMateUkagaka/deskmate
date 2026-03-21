export interface SlashCommand {
  name: string
  description: string
}

export interface GhostPosition {
  x: number
  y: number
}

export type PlacementOrigin = 'center' | 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'

export interface UiPlacement {
  x: number
  y: number
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

export interface InputTheme {
  max_width: number | null
  max_height: number | null
}

export interface IdleAnimation {
  file: string
  duration_ms: number
}

export interface SkinInfo {
  id: string
  name: string
  author: string | null
  version: string | null
  path: string
  /** Available emotion names from the skin manifest */
  emotions: string[]
  bubble_placement: UiPlacement | null
  input_placement: UiPlacement | null
  bubble_theme: BubbleTheme | null
  input_theme: InputTheme | null
  /** Idle animation clips (empty if skin has none) */
  idle_animations: IdleAnimation[]
  /** Seconds between idle animations (default 30) */
  idle_interval_seconds: number
  source: string          // "bundled" | "community"
  format_version: number  // 1 = static PNGs (current), 2+ = future
}

export interface OcsContentItem {
  id: string
  name: string
  version: string
  personid: string
  created: string
  changed: string
  downloads: number
  score: number
  summary: string
  description: string
  tags: string
  previewpic1: string
  smallpreviewpic1: string
  downloadlink1: string
  downloadname1: string
  downloadsize1: number
  downloadmd5sum1: string
}

export interface OcsBrowseResult {
  status: string
  statuscode: number
  totalitems: number
  itemsperpage: number
  data: OcsContentItem[]
}

export interface OcsBrowseParams {
  categories: string
  tags: string
  search: string
  sortmode: string
  page: number
  pagesize: number
}

export interface SkinDownloadProgress {
  downloaded: number
  total: number | null
}

export interface QuakeTerminalConfig {
  enabled: boolean
  hotkey: string
  terminal_emulator: string | null
  command: string
  height_percent: number
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
  popup_margin_top: number
  popup_margin_bottom: number
  popup_margin_left: number
  popup_margin_right: number
  quake_terminal: QuakeTerminalConfig
}
