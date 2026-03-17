import { invoke } from '@tauri-apps/api/core'

/**
 * Log to /tmp/debug.log via Rust backend.
 * Use this instead of console.log — WebKitGTK transparent windows
 * may not show console output in the web inspector.
 */
export function debugLog(...args: unknown[]): void {
  const msg = args.map(a => typeof a === 'string' ? a : JSON.stringify(a)).join(' ') + '\n'
  invoke('debug_log', { content: msg }).catch(() => {})
}
