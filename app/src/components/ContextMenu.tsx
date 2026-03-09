import { useEffect, type CSSProperties } from 'react'

interface ContextMenuProps {
  x: number
  y: number
  onClose: () => void
  onChangeSkin: () => void
  onSettings: () => void
}

export function ContextMenu({ x, y, onClose, onChangeSkin, onSettings }: ContextMenuProps) {
  useEffect(() => {
    const handler = () => onClose()
    window.addEventListener('mousedown', handler)
    return () => window.removeEventListener('mousedown', handler)
  }, [onClose])

  const menuStyle: CSSProperties = {
    position: 'fixed',
    left: x,
    top: y,
    background: 'rgba(255,255,255,0.94)',
    backdropFilter: 'blur(12px)',
    borderRadius: 10,
    boxShadow: '0 6px 24px rgba(0,0,0,0.18)',
    minWidth: 160,
    zIndex: 9999,
    overflow: 'hidden',
    pointerEvents: 'auto',
  }

  const itemStyle: CSSProperties = {
    padding: '10px 16px',
    fontSize: 13,
    cursor: 'pointer',
    color: '#1a1a1a',
    display: 'block',
    width: '100%',
    background: 'transparent',
    border: 'none',
    textAlign: 'left',
    transition: 'background 0.1s',
  }

  const separatorStyle: CSSProperties = {
    height: 1,
    background: 'rgba(0,0,0,0.08)',
    margin: '2px 0',
  }

  const handleClick = (fn: () => void) => (e: React.MouseEvent) => {
    e.stopPropagation()
    fn()
    onClose()
  }

  return (
    <div style={menuStyle} onMouseDown={(e) => e.stopPropagation()}>
      <button
        style={itemStyle}
        onClick={handleClick(onChangeSkin)}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0,0,0,0.05)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        Change Skin
      </button>
      <button
        style={itemStyle}
        onClick={handleClick(() => {
          // placeholder: open external URL
        })}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0,0,0,0.05)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        Buy Skins
      </button>
      <div style={separatorStyle} />
      <button
        style={itemStyle}
        onClick={handleClick(onSettings)}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0,0,0,0.05)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        Settings
      </button>
    </div>
  )
}
