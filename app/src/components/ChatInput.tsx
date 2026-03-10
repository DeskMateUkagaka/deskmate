import { useState, useEffect, useRef, useCallback, type CSSProperties, type KeyboardEvent } from 'react'
import { getCurrentWindow, PhysicalSize, PhysicalPosition } from '@tauri-apps/api/window'
import type { ConnectionStatus } from '../hooks/useOpenClaw'

const STATUS_COLORS: Record<ConnectionStatus, string> = {
  connected: '#4caf50',
  connecting: '#ff9800',
  disconnected: '#9e9e9e',
  error: '#f44336',
}

async function nudgeWindowRepaint() {
  const win = getCurrentWindow()
  const pos = await win.outerPosition()
  const size = await win.outerSize()
  await win.setSize(new PhysicalSize(size.width + 1, size.height + 1))
  await new Promise(r => requestAnimationFrame(r))
  await win.setSize(new PhysicalSize(size.width, size.height))
  await win.setPosition(new PhysicalPosition(pos.x, pos.y))
}

interface ChatInputProps {
  isOpen: boolean
  connectionStatus: ConnectionStatus
  viewportWidth: number
  imageBottom: number | null
  onSend: (text: string) => void
  onClose: () => void
}

export function ChatInput({
  isOpen,
  connectionStatus,
  viewportWidth,
  imageBottom,
  onSend,
  onClose,
}: ChatInputProps) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const wasOpenRef = useRef(false)

  useEffect(() => {
    if (isOpen) {
      setValue('')
      const tryFocus = () => inputRef.current?.focus()
      tryFocus()
      const t1 = setTimeout(tryFocus, 50)
      const t2 = setTimeout(tryFocus, 150)
      wasOpenRef.current = true
      return () => { clearTimeout(t1); clearTimeout(t2) }
    } else if (wasOpenRef.current) {
      // Closed by any mechanism — nudge to clear bleed
      wasOpenRef.current = false
      nudgeWindowRepaint()
    }
  }, [isOpen])

  const handleClose = useCallback(() => {
    onClose()
  }, [onClose])

  // ESC to close
  useEffect(() => {
    if (!isOpen) return
    const handleKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') handleClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [isOpen, handleClose])

  if (!isOpen) return null

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && value.trim()) {
      onSend(value.trim())
      setValue('')
      handleClose()
    }
  }

  const inputWidth = Math.min(260, viewportWidth - 20)

  // Position just below the ghost image, or fallback to 80% from top
  const topPos = imageBottom != null ? imageBottom + 4 : window.innerHeight * 0.8

  const containerStyle: CSSProperties = {
    position: 'fixed',
    top: topPos,
    left: (viewportWidth - inputWidth) / 2,
    width: inputWidth,
    zIndex: 2000,
    pointerEvents: 'auto',
  }

  const wrapperStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    background: 'rgba(255,255,255,0.92)',
    backdropFilter: 'blur(10px)',
    borderRadius: 24,
    padding: '6px 12px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.18)',
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
    <div style={containerStyle}>
      <div style={wrapperStyle}>
        <span style={dotStyle} title={connectionStatus} />
        <input
          ref={inputRef}
          style={inputStyle}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Say something…"
        />
        <button style={closeBtnStyle} onClick={(e) => { e.stopPropagation(); handleClose() }} title="Close">✕</button>
      </div>
    </div>
  )
}
