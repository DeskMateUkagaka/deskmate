import { useState, useEffect, type CSSProperties } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { emit, listen } from '@tauri-apps/api/event'
import { getCurrentWindow } from '@tauri-apps/api/window'
import type { SkinInfo } from '../types'


export function SkinPickerWindow() {
  const [skins, setSkins] = useState<SkinInfo[]>([])
  const [currentSkinId, setCurrentSkinId] = useState('')

  useEffect(() => {
    invoke<SkinInfo[]>('list_skins').then(setSkins)
    invoke<SkinInfo>('get_current_skin').then((s) => setCurrentSkinId(s.id)).catch(() => {})
  }, [])

  // Auto-refresh when a new skin is installed from Get Skins
  useEffect(() => {
    const unlisten = listen('skin-installed', () => {
      invoke<SkinInfo[]>('list_skins').then(setSkins)
    })
    return () => { unlisten.then(fn => fn()) }
  }, [])

  const win = getCurrentWindow()

  const handleSelect = async (id: string) => {
    await invoke('switch_skin', { skinId: id })
    await emit('skin-selected', { id })
    win.hide()
  }

  const handleClose = () => win.hide()

  const panelStyle: CSSProperties = {
    background: '#fff',
    padding: 20,
    display: 'flex',
    flexDirection: 'column',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
    height: '100vh',
    overflow: 'hidden',
  }

  const headerStyle: CSSProperties = {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14,
  }
  const titleStyle: CSSProperties = { fontSize: 15, fontWeight: 600, color: '#1a1a1a' }
  const closeButtonStyle: CSSProperties = {
    background: 'transparent', border: 'none', cursor: 'pointer',
    fontSize: 18, color: '#888', lineHeight: 1, padding: 2,
  }
  const gridStyle: CSSProperties = {
    display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10,
    overflowY: 'auto', flex: 1,
  }
  const skinCardStyle = (isSelected: boolean): CSSProperties => ({
    border: isSelected ? '2px solid #3060c0' : '2px solid transparent',
    borderRadius: 10, padding: 10, cursor: 'pointer',
    background: isSelected ? 'rgba(80,120,220,0.08)' : 'rgba(0,0,0,0.04)',
    textAlign: 'center', transition: 'border-color 0.15s',
  })
  const skinNameStyle: CSSProperties = {
    fontSize: 12, fontWeight: 500, color: '#333', marginTop: 4,
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  }
  const placeholderStyle: CSSProperties = {
    width: '100%', height: 80, background: 'rgba(0,0,0,0.06)',
    borderRadius: 6, display: 'flex', alignItems: 'center',
    justifyContent: 'center', fontSize: 24, color: '#bbb',
  }

  return (
    <div style={panelStyle}>
      <div style={headerStyle}>
        <span style={titleStyle}>Choose Skin</span>
        <button style={closeButtonStyle} onClick={handleClose}>×</button>
      </div>
      <div style={gridStyle}>
        {skins.length === 0 && (
          <div style={{ gridColumn: '1/-1', textAlign: 'center', color: '#888', fontSize: 13, padding: 20 }}>
            No skins installed
          </div>
        )}
        {skins.map((skin) => (
          <div key={skin.id} style={skinCardStyle(skin.id === currentSkinId)} onClick={() => handleSelect(skin.id)}>
            <div style={placeholderStyle}>🎭</div>
            <div style={skinNameStyle}>{skin.name}</div>
            {skin.author && (
              <div style={{ fontSize: 10, color: '#999', marginTop: 2 }}>by {skin.author}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
