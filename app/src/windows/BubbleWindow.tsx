import { useState, useEffect, useRef, type CSSProperties } from 'react'
import { listen, emit } from '@tauri-apps/api/event'
import { getCurrentWindow } from '@tauri-apps/api/window'

interface BubbleData {
  text: string
  isStreaming: boolean
  isVisible: boolean
  isPinned: boolean
  timeoutMs: number
  finalizedAt: number | null
}

export function BubbleWindow() {
  const [data, setData] = useState<BubbleData>({
    text: '',
    isStreaming: false,
    isVisible: false,
    isPinned: false,
    timeoutMs: 60000,
    finalizedAt: null,
  })
  const [progress, setProgress] = useState(1)
  const win = getCurrentWindow()

  // Listen for bubble state updates from main window
  useEffect(() => {
    let unlisten: (() => void) | undefined
    listen<BubbleData>('bubble-update', (event) => {
      setData(event.payload)
      if (!event.payload.isVisible) {
        win.hide()
      }
    }).then((fn) => { unlisten = fn })
    return () => unlisten?.()
  }, [win])

  // Show window when visible
  useEffect(() => {
    if (data.isVisible) {
      win.show().catch(() => {})
    }
  }, [data.isVisible, win])

  // Progress bar countdown
  useEffect(() => {
    if (!data.finalizedAt || data.isPinned) {
      setProgress(1)
      return
    }
    const interval = setInterval(() => {
      const elapsed = Date.now() - data.finalizedAt!
      const remaining = Math.max(0, 1 - elapsed / data.timeoutMs)
      setProgress(remaining)
      if (remaining <= 0) clearInterval(interval)
    }, 50)
    return () => clearInterval(interval)
  }, [data.finalizedAt, data.timeoutMs, data.isPinned])

  // Dismiss on 'x' key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'x' && data.isVisible) {
        emit('bubble-action', { action: 'dismiss' })
      }
    }
    document.addEventListener('keyup', handler)
    return () => document.removeEventListener('keyup', handler)
  }, [data.isVisible])

  if (!data.isVisible) return null

  const outerStyle: CSSProperties = {
    width: '100vw',
    height: '100vh',
    background: 'transparent',
    display: 'flex',
    alignItems: 'flex-end',
    padding: 4,
  }

  const bubbleStyle: CSSProperties = {
    background: '#fff',
    borderRadius: 12,
    padding: '12px 14px',
    border: '1px solid #d0d0d0',
    position: 'relative',
    fontSize: 13,
    lineHeight: 1.5,
    color: '#1a1a1a',
    wordBreak: 'break-word',
    overflow: 'hidden',
    width: '100%',
  }

  const actionsStyle: CSSProperties = {
    display: 'flex',
    gap: 6,
    marginTop: 10,
    flexWrap: 'wrap',
  }

  const pillStyle: CSSProperties = {
    padding: '4px 10px',
    borderRadius: 20,
    border: 'none',
    cursor: 'pointer',
    fontSize: 11,
    fontWeight: 500,
    transition: 'background 0.15s',
  }

  const primaryPillStyle: CSSProperties = {
    ...pillStyle,
    background: 'rgba(80, 120, 220, 0.15)',
    color: '#3060c0',
  }

  const secondaryPillStyle: CSSProperties = {
    ...pillStyle,
    background: 'rgba(0,0,0,0.07)',
    color: '#555',
  }

  const progressBarContainerStyle: CSSProperties = {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: 3,
    background: 'rgba(0,0,0,0.06)',
  }

  const progressBarStyle: CSSProperties = {
    height: '100%',
    width: `${progress * 100}%`,
    background: 'rgba(80, 120, 220, 0.4)',
    borderRadius: '0 0 12px 12px',
    transition: 'width 0.1s linear',
  }

  const showProgressBar = !data.isStreaming && !data.isPinned && data.finalizedAt !== null

  return (
    <div style={outerStyle}>
      <div style={bubbleStyle}>
        <div style={{ minHeight: 20 }}>
          {data.text}
          {data.isStreaming && (
            <span style={{ display: 'inline-block', marginLeft: 2, animation: 'blink 1s step-end infinite' }}>▋</span>
          )}
        </div>
        {!data.isStreaming && (
          <div style={actionsStyle}>
            {!data.isPinned && (
              <button style={primaryPillStyle} onClick={() => emit('bubble-action', { action: 'tell-me-more' })}>
                Tell me more
              </button>
            )}
            {!data.isPinned && (
              <button style={primaryPillStyle} onClick={() => emit('bubble-action', { action: 'pin' })}>
                Pin
              </button>
            )}
            <button style={secondaryPillStyle} onClick={() => emit('bubble-action', { action: 'dismiss' })}>
              Dismiss (x)
            </button>
          </div>
        )}
        {showProgressBar && (
          <div style={progressBarContainerStyle}>
            <div style={progressBarStyle} />
          </div>
        )}
      </div>
    </div>
  )
}
