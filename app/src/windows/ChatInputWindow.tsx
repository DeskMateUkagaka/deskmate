import { useState, useEffect, useRef, useCallback, type CSSProperties, type KeyboardEvent } from 'react'
import { emit, listen } from '@tauri-apps/api/event'
import { getCurrentWindow } from '@tauri-apps/api/window'
import { LogicalSize } from '@tauri-apps/api/window'
import type { ConnectionStatus } from '../hooks/useOpenClaw'

const STATUS_COLORS: Record<ConnectionStatus, string> = {
  connected: '#4caf50',
  connecting: '#ff9800',
  disconnected: '#9e9e9e',
  error: '#f44336',
}

const MIN_WIDTH = 280
const MIN_HEIGHT = 44
const DEFAULT_MAX_WIDTH = 640
const DEFAULT_MAX_HEIGHT = 480

interface InputConfig {
  maxWidth: number
  maxHeight: number
}

export function ChatInputWindow() {
  const [value, setValue] = useState('')
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected')
  const [config, setConfig] = useState<InputConfig>({ maxWidth: DEFAULT_MAX_WIDTH, maxHeight: DEFAULT_MAX_HEIGHT })
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const win = getCurrentWindow()

  // Focus textarea when window becomes visible
  useEffect(() => {
    let unlisten: (() => void) | undefined
    win.onFocusChanged(({ payload: focused }) => {
      if (focused) {
        setValue('')
        textareaRef.current?.focus()
      }
    }).then((fn) => { unlisten = fn })
    setTimeout(() => textareaRef.current?.focus(), 50)
    return () => unlisten?.()
  }, [win])

  // Listen for connection status updates from main window
  useEffect(() => {
    let unlisten: (() => void) | undefined
    listen<ConnectionStatus>('connection-status', (event) => {
      setConnectionStatus(event.payload)
    }).then((fn) => { unlisten = fn })
    return () => unlisten?.()
  }, [])

  // Listen for input config from main window
  useEffect(() => {
    let unlisten: (() => void) | undefined
    listen<InputConfig>('input-config', (event) => {
      setConfig(event.payload)
    }).then((fn) => { unlisten = fn })
    return () => unlisten?.()
  }, [])

  // ESC to close
  useEffect(() => {
    const handleKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') win.hide()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [win])

  // Auto-resize window to fit textarea content
  const resizeToFit = useCallback(async () => {
    const ta = textareaRef.current
    if (!ta) return

    // Reset height to measure scrollHeight accurately
    ta.style.height = '0px'
    const scrollH = ta.scrollHeight
    const contentHeight = Math.min(scrollH, config.maxHeight - 20) // 20 = padding
    ta.style.height = contentHeight + 'px'

    // Compute desired window size
    // Width: start at MIN_WIDTH, grow to maxWidth based on longest line
    const lines = ta.value.split('\n')
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    let longestLinePx = 0
    if (ctx) {
      ctx.font = '13px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif'
      for (const line of lines) {
        const w = ctx.measureText(line).width
        if (w > longestLinePx) longestLinePx = w
      }
    }
    // Add padding (12px left + 12px right + dot 8px + gap 6px + close btn ~20px + gap 6px = ~64px)
    const desiredWidth = Math.max(MIN_WIDTH, Math.min(longestLinePx + 64, config.maxWidth))
    // panel padding top/bottom 6+6=12, border 2, plus textarea height
    const desiredHeight = Math.max(MIN_HEIGHT, contentHeight + 14)

    const finalWidth = Math.ceil(desiredWidth)
    const finalHeight = Math.ceil(desiredHeight)
    await win.setSize(new LogicalSize(finalWidth, finalHeight))
    // Notify main window so it can reposition with margin clamping
    await emit('input-resized', { width: finalWidth, height: finalHeight })
  }, [win, config])

  useEffect(() => {
    resizeToFit()
  }, [value, resizeToFit])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      emit('chat-send', { text: value.trim() })
      setValue('')
      win.hide()
    }
  }

  const handleClose = () => win.hide()

  const outerStyle: CSSProperties = {
    width: '100vw',
    height: '100vh',
    background: 'transparent',
    display: 'flex',
    alignItems: 'flex-end',
  }

  const panelStyle: CSSProperties = {
    background: '#fff',
    display: 'flex',
    alignItems: 'flex-start',
    gap: 6,
    padding: '6px 12px',
    width: '100%',
    borderRadius: 12,
    border: '1px solid #d0d0d0',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
  }

  const textareaStyle: CSSProperties = {
    flex: 1,
    border: 'none',
    background: 'transparent',
    outline: 'none',
    fontSize: 13,
    color: '#1a1a1a',
    resize: 'none',
    lineHeight: '20px',
    padding: 0,
    margin: 0,
    fontFamily: 'inherit',
    overflow: 'auto',
  }

  const dotStyle: CSSProperties = {
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: STATUS_COLORS[connectionStatus],
    flexShrink: 0,
    marginTop: 6,
  }

  const closeBtnStyle: CSSProperties = {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    fontSize: 14,
    color: '#999',
    padding: '0 2px',
    lineHeight: 1,
    flexShrink: 0,
    marginTop: 2,
  }

  return (
    <div style={outerStyle}>
      <div style={panelStyle}>
        <span style={dotStyle} title={connectionStatus} />
        <textarea
          ref={textareaRef}
          style={textareaStyle}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Say something... (Shift+Enter for newline)"
          rows={1}
        />
        <button style={closeBtnStyle} onClick={handleClose} title="Close">✕</button>
      </div>
    </div>
  )
}
