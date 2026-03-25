import { invoke } from '@tauri-apps/api/core'

/**
 * Log to /tmp/deskmate.log via Rust backend.
 * Use this instead of console.log — WebKitGTK transparent windows
 * may not show console output in the web inspector.
 */
export function debugLog(...args: unknown[]): void {
  const now = new Date()
  const ts = now.toTimeString().slice(0, 8) + '.' + String(now.getMilliseconds()).padStart(3, '0')
  const msg = ts + ' ' + args.map(a => typeof a === 'string' ? a : JSON.stringify(a)).join(' ') + '\n'
  invoke('debug_log', { content: msg }).catch(() => {})
}
