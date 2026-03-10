import { useState, useEffect, useRef, type CSSProperties, type KeyboardEvent } from 'react'
import type { ConnectionStatus } from '../hooks/useOpenClaw'

interface ChatInputProps {
  isOpen: boolean
  connectionStatus: ConnectionStatus
  viewportWidth: number
  onSend: (text: string) => void
  onClose: () => void
}

const STATUS_COLORS: Record<ConnectionStatus, string> = {
  connected: '#4caf50',
  connecting: '#ff9800',
  disconnected: '#9e9e9e',
  error: '#f44336',
}

export function ChatInput({
  isOpen,
  connectionStatus,
  viewportWidth,
  onSend,
  onClose,
}: ChatInputProps) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isOpen) {
      setValue('')
      const tryFocus = () => inputRef.current?.focus()
      tryFocus()
      const t1 = setTimeout(tryFocus, 50)
      const t2 = setTimeout(tryFocus, 150)
      return () => { clearTimeout(t1); clearTimeout(t2) }
    }
  }, [isOpen])

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && value.trim()) {
      onSend(value.trim())
      setValue('')
      onClose()
    }
  }

  const inputWidth = Math.min(260, viewportWidth - 20)
  const containerStyle: CSSProperties = {
    position: 'fixed',
    left: (viewportWidth - inputWidth) / 2,
    top: isOpen ? 10 : -100,
    width: inputWidth,
    zIndex: 2000,
    pointerEvents: isOpen ? 'auto' : 'none',
    opacity: isOpen ? 1 : 0,
    transition: 'top 0.15s ease, opacity 0.15s ease',
  }

  const wrapperStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    background: 'rgba(255,255,255,0.90)',
    backdropFilter: 'blur(10px)',
    borderRadius: 24,
    padding: '6px 12px',
    boxShadow: '0 4px 16px rgba(0,0,0,0.16)',
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
          tabIndex={isOpen ? 0 : -1}
        />
        <button style={closeBtnStyle} onClick={onClose} title="Close" tabIndex={isOpen ? 0 : -1}>✕</button>
      </div>
    </div>
  )
}
