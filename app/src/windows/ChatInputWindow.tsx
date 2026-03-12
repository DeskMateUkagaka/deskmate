import { useState, useEffect, useRef, type CSSProperties, type KeyboardEvent } from 'react'
import { emit, listen } from '@tauri-apps/api/event'
import { getCurrentWindow } from '@tauri-apps/api/window'
import type { ConnectionStatus } from '../hooks/useOpenClaw'

const STATUS_COLORS: Record<ConnectionStatus, string> = {
  connected: '#4caf50',
  connecting: '#ff9800',
  disconnected: '#9e9e9e',
  error: '#f44336',
}

export function ChatInputWindow() {
  const [value, setValue] = useState('')
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected')
  const inputRef = useRef<HTMLInputElement>(null)
  const win = getCurrentWindow()

  // Focus input when window becomes visible
  useEffect(() => {
    let unlisten: (() => void) | undefined
    win.onFocusChanged(({ payload: focused }) => {
      if (focused) {
        setValue('')
        inputRef.current?.focus()
      }
    }).then((fn) => { unlisten = fn })
    // Also focus on mount
    setTimeout(() => inputRef.current?.focus(), 50)
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

  // ESC to close
  useEffect(() => {
    const handleKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') win.hide()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [win])

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
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
    alignItems: 'center',
    gap: 6,
    padding: '6px 12px',
    width: '100%',
    borderRadius: 24,
    border: '1px solid #d0d0d0',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
  }

  const inputStyle: CSSProperties = {
    flex: 1,
    border: 'none',
    background: 'transparent',
    outline: 'none',
    fontSize: 13,
    color: '#1a1a1a',
  }

  const dotStyle: CSSProperties = {
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: STATUS_COLORS[connectionStatus],
    flexShrink: 0,
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
  }

  return (
    <div style={outerStyle}>
      <div style={panelStyle}>
        <span style={dotStyle} title={connectionStatus} />
        <input
          ref={inputRef}
          style={inputStyle}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Say something..."
        />
        <button style={closeBtnStyle} onClick={handleClose} title="Close">✕</button>
      </div>
    </div>
  )
}
