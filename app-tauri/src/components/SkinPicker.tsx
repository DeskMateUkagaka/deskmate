import { useState, type CSSProperties } from 'react'
import { convertFileSrc } from '@tauri-apps/api/core'
import type { SkinInfo } from '../types'

interface SkinPickerProps {
  skins: SkinInfo[]
  currentSkinId: string
  onSelect: (id: string) => void
  onClose: () => void
}

const previewImgStyle: CSSProperties = {
  width: '100%', height: 80, objectFit: 'contain', borderRadius: 6,
}

function SkinPreview({ path }: { path: string }) {
  const [failed, setFailed] = useState(false)
  const src = convertFileSrc(path + '/preview.png')

  if (failed) return <div style={placeholderFallbackStyle}>🎭</div>
  return <img src={src} style={previewImgStyle} onError={() => setFailed(true)} />
}

const placeholderFallbackStyle: CSSProperties = {
  width: '100%', height: 80, background: 'rgba(0,0,0,0.06)',
  borderRadius: 6, display: 'flex', alignItems: 'center',
  justifyContent: 'center', fontSize: 24, color: '#bbb',
}

export function SkinPicker({ skins, currentSkinId, onSelect, onClose }: SkinPickerProps) {
  const overlayStyle: CSSProperties = {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.35)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 5000,
    pointerEvents: 'auto',
  }

  const panelStyle: CSSProperties = {
    background: 'rgba(255,255,255,0.96)',
    backdropFilter: 'blur(16px)',
    borderRadius: 14,
    padding: 20,
    width: 320,
    maxHeight: 420,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: '0 8px 32px rgba(0,0,0,0.22)',
  }

  const headerStyle: CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  }

  const titleStyle: CSSProperties = {
    fontSize: 15,
    fontWeight: 600,
    color: '#1a1a1a',
  }

  const closeButtonStyle: CSSProperties = {
    background: 'transparent',
    border: 'none',
    cursor: 'pointer',
    fontSize: 18,
    color: '#888',
    lineHeight: 1,
    padding: 2,
  }

  const gridStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: 10,
    overflowY: 'auto',
  }

  const skinCardStyle = (isSelected: boolean): CSSProperties => ({
    border: isSelected ? '2px solid #3060c0' : '2px solid transparent',
    borderRadius: 10,
    padding: 10,
    cursor: 'pointer',
    background: isSelected ? 'rgba(80,120,220,0.08)' : 'rgba(0,0,0,0.04)',
    textAlign: 'center',
    transition: 'border-color 0.15s',
  })

  const skinNameStyle: CSSProperties = {
    fontSize: 12,
    fontWeight: 500,
    color: '#333',
    marginTop: 4,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  }

  return (
    <div style={overlayStyle} onMouseDown={onClose}>
      <div style={panelStyle} onMouseDown={(e) => e.stopPropagation()}>
        <div style={headerStyle}>
          <span style={titleStyle}>Choose Skin</span>
          <button style={closeButtonStyle} onClick={onClose}>×</button>
        </div>
        <div style={gridStyle}>
          {skins.length === 0 && (
            <div style={{ gridColumn: '1/-1', textAlign: 'center', color: '#888', fontSize: 13, padding: 20 }}>
              No skins installed
            </div>
          )}
          {skins.map((skin) => (
            <div
              key={skin.id}
              style={skinCardStyle(skin.id === currentSkinId)}
              onClick={() => onSelect(skin.id)}
            >
              <SkinPreview path={skin.path} />
              <div style={skinNameStyle}>{skin.name}</div>
              {skin.description && (
                <div style={{ fontSize: 10, color: '#666', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{skin.description}</div>
              )}
              {skin.author && (
                <div style={{ fontSize: 10, color: '#999', marginTop: 2 }}>by {skin.author}</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
