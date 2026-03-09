import type { CSSProperties } from 'react'

interface ActionButtonsProps {
  onTellMeMore: () => void
  onDismiss: () => void
}

export function ActionButtons({ onTellMeMore, onDismiss }: ActionButtonsProps) {
  const containerStyle: CSSProperties = {
    display: 'flex',
    gap: 6,
    marginTop: 8,
  }

  const pillBase: CSSProperties = {
    padding: '4px 12px',
    borderRadius: 20,
    border: 'none',
    cursor: 'pointer',
    fontSize: 11,
    fontWeight: 500,
  }

  const primaryStyle: CSSProperties = {
    ...pillBase,
    background: 'rgba(80, 120, 220, 0.15)',
    color: '#3060c0',
  }

  const secondaryStyle: CSSProperties = {
    ...pillBase,
    background: 'rgba(0,0,0,0.07)',
    color: '#555',
  }

  return (
    <div style={containerStyle}>
      <button style={primaryStyle} onClick={onTellMeMore}>
        Tell me more
      </button>
      <button style={secondaryStyle} onClick={onDismiss}>
        Dismiss
      </button>
    </div>
  )
}
