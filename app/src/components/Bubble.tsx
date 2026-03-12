import { useState, useEffect, type CSSProperties } from 'react'

interface BubbleProps {
  text: string
  isStreaming: boolean
  isVisible: boolean
  isPinned: boolean
  bubbleState: string
  viewportWidth: number
  timeoutMs: number
  finalizedAt: number | null
  onDismiss: () => void
  onPin: () => void
  onTellMeMore: () => void
}

export function Bubble({
  text,
  isStreaming,
  isVisible,
  isPinned,
  bubbleState,
  viewportWidth,
  timeoutMs,
  finalizedAt,
  onDismiss,
  onPin,
  onTellMeMore,
}: BubbleProps) {
  // Progress bar countdown (0.0 to 1.0, where 1.0 = full)
  const [progress, setProgress] = useState(1)

  useEffect(() => {
    if (!finalizedAt || isPinned) {
      setProgress(1)
      return
    }
    const interval = setInterval(() => {
      const elapsed = Date.now() - finalizedAt
      const remaining = Math.max(0, 1 - elapsed / timeoutMs)
      setProgress(remaining)
      if (remaining <= 0) clearInterval(interval)
    }, 50)
    return () => clearInterval(interval)
  }, [finalizedAt, timeoutMs, isPinned])

  if (!isVisible) return null

  const bubbleWidth = Math.min(260, viewportWidth - 20)

  const containerStyle: CSSProperties = {
    position: 'fixed',
    top: 10,
    left: (viewportWidth - bubbleWidth) / 2,
    width: bubbleWidth,
    zIndex: 1000,
    pointerEvents: 'auto',
  }

  const bubbleStyle: CSSProperties = {
    background: 'rgba(255, 255, 255, 0.92)',
    backdropFilter: 'blur(8px)',
    borderRadius: 12,
    padding: '12px 14px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.18)',
    position: 'relative',
    fontSize: 13,
    lineHeight: 1.5,
    color: '#1a1a1a',
    wordBreak: 'break-word',
    overflow: 'hidden',
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

  const showProgressBar = !isStreaming && !isPinned && finalizedAt !== null

  return (
    <div style={containerStyle}>
      <div style={bubbleStyle}>
        <div style={{ minHeight: 20 }}>
          {text}
          {isStreaming && (
            <span style={{ display: 'inline-block', marginLeft: 2, animation: 'blink 1s step-end infinite' }}>▋</span>
          )}
        </div>
        {!isStreaming && (
          <div style={actionsStyle}>
            {!isPinned && (
              <button style={primaryPillStyle} onClick={(e) => { e.stopPropagation(); onTellMeMore() }}>
                Tell me more
              </button>
            )}
            {!isPinned && (
              <button style={primaryPillStyle} onClick={(e) => { e.stopPropagation(); onPin() }}>
                Pin
              </button>
            )}
            <button style={secondaryPillStyle} onClick={(e) => { e.stopPropagation(); onDismiss() }}>
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
