import type { CSSProperties } from 'react'

interface BubbleProps {
  text: string
  isTruncated: boolean
  isStreaming: boolean
  isVisible: boolean
  bubbleState: string
  ghostX: number
  ghostWidth: number
  screenWidth: number
  onExpand: () => void
  onDismiss: () => void
  onTellMeMore: () => void
}

export function Bubble({
  text,
  isTruncated,
  isStreaming,
  isVisible,
  bubbleState,
  ghostX,
  ghostWidth,
  screenWidth,
  onExpand,
  onDismiss,
  onTellMeMore,
}: BubbleProps) {
  if (!isVisible) return null

  // Determine if bubble should appear to the left or right of ghost
  const ghostCenterX = ghostX + ghostWidth / 2
  const openRight = ghostCenterX < screenWidth / 2
  const bubbleWidth = 260

  const containerStyle: CSSProperties = {
    position: 'fixed',
    top: 20,
    ...(openRight
      ? { left: ghostX + ghostWidth + 12 }
      : { left: ghostX - bubbleWidth - 12 }),
    width: bubbleWidth,
    zIndex: 1000,
    opacity: bubbleState === 'dismissing' ? 0 : 1,
    transition: 'opacity 0.3s ease',
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
  }

  const tailStyle: CSSProperties = {
    position: 'absolute',
    top: 16,
    ...(openRight
      ? { left: -8, borderRight: '8px solid rgba(255,255,255,0.92)', borderTop: '6px solid transparent', borderBottom: '6px solid transparent' }
      : { right: -8, borderLeft: '8px solid rgba(255,255,255,0.92)', borderTop: '6px solid transparent', borderBottom: '6px solid transparent' }),
    width: 0,
    height: 0,
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

  return (
    <div style={containerStyle}>
      <div style={bubbleStyle}>
        <div style={tailStyle} />
        <div style={{ minHeight: 20 }}>
          {text}
          {isStreaming && (
            <span style={{ display: 'inline-block', marginLeft: 2, animation: 'blink 1s step-end infinite' }}>▋</span>
          )}
        </div>
        {!isStreaming && (
          <div style={actionsStyle}>
            <button style={primaryPillStyle} onClick={onTellMeMore}>
              Tell me more
            </button>
            {isTruncated && (
              <button style={primaryPillStyle} onClick={onExpand}>
                Expand
              </button>
            )}
            <button style={secondaryPillStyle} onClick={onDismiss}>
              Dismiss
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
