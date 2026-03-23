import { useEffect, type CSSProperties } from 'react'
import { emit } from '@tauri-apps/api/event'
import { getCurrentWindow } from '@tauri-apps/api/window'

const win = getCurrentWindow()

// Hide when window loses focus (user clicked elsewhere)
// Guard: only attach for the actual context-menu window, not when imported by main
if (win.label === 'context-menu') {
  win.onFocusChanged(({ payload: focused }) => {
    if (!focused) win.hide()
  })
  win.onCloseRequested((e) => {
    e.preventDefault()
    win.hide()
  })
}

export function ContextMenuWindow() {
  useEffect(() => {
    const handler = (e: MouseEvent) => e.preventDefault()
    window.addEventListener('contextmenu', handler)
    return () => window.removeEventListener('contextmenu', handler)
  }, [])

  const doAction = (action: string) => {
    emit('menu-action', { action })
    win.hide()
  }

  const menuStyle: CSSProperties = {
    background: 'rgba(255,255,255,0.96)',
    borderRadius: 10,
    overflow: 'hidden',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
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
    fontFamily: 'inherit',
  }

  const separatorStyle: CSSProperties = {
    height: 1,
    background: 'rgba(0,0,0,0.08)',
    margin: '2px 0',
  }

  return (
    <div style={menuStyle}>
      <button
        style={itemStyle}
        onClick={() => doAction('change-skin')}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0,0,0,0.05)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        Change Skin
      </button>
      <button
        style={itemStyle}
        onClick={async () => {
          const { WebviewWindow } = await import('@tauri-apps/api/webviewWindow')
          const gsWin = await WebviewWindow.getByLabel('get-skins')
          if (gsWin) { await gsWin.show(); await gsWin.setFocus() }
          win.hide()
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0,0,0,0.05)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        Get Skins
      </button>
      <div style={separatorStyle} />
      <button
        style={itemStyle}
        onClick={() => doAction('settings')}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0,0,0,0.05)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        Settings
      </button>
    </div>
  )
}
