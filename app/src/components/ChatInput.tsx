import { useState, useEffect, useRef, type CSSProperties, type KeyboardEvent } from 'react'
import type { ConnectionStatus } from '../hooks/useOpenClaw'

interface ChatInputProps {
  isOpen: boolean
  connectionStatus: ConnectionStatus
  ghostX: number
  ghostY: number
  ghostWidth: number
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
  ghostX,
  ghostY,
  ghostWidth,
  onSend,
  onClose,
}: ChatInputProps) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isOpen) {
      setValue('')
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && value.trim()) {
      onSend(value.trim())
      setValue('')
      onClose()
    } else if (e.key === 'Escape') {
      onClose()
    }
  }

  const containerStyle: CSSProperties = {
    position: 'fixed',
    left: ghostX + ghostWidth / 2 - 130,
    top: ghostY - 52,
    width: 260,
    zIndex: 2000,
    pointerEvents: 'auto',
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
      </div>
    </div>
  )
}
