import { useState, type CSSProperties } from 'react'
import type { Settings } from '../types'

interface SettingsPanelProps {
  settings: Settings
  onSave: (partial: Partial<Settings>) => void
  onClose: () => void
}

export function SettingsPanel({ settings, onSave, onClose }: SettingsPanelProps) {
  const [gatewayUrl, setGatewayUrl] = useState(settings.gateway_url)
  const [gatewayToken, setGatewayToken] = useState(settings.gateway_token)
  const [bubbleTimeout, setBubbleTimeout] = useState(Math.round(settings.bubble_timeout_ms / 1000))
  const [proactiveEnabled, setProactiveEnabled] = useState(settings.proactive_enabled)
  const [proactiveInterval, setProactiveInterval] = useState(settings.proactive_interval_mins)

  const handleSave = () => {
    onSave({
      gateway_url: gatewayUrl,
      gateway_token: gatewayToken,
      bubble_timeout_ms: bubbleTimeout * 1000,
      proactive_enabled: proactiveEnabled,
      proactive_interval_mins: proactiveInterval,
    })
    onClose()
  }

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
    padding: 22,
    width: 340,
    boxShadow: '0 8px 32px rgba(0,0,0,0.22)',
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
  }

  const headerStyle: CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
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

  const fieldStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  }

  const labelStyle: CSSProperties = {
    fontSize: 12,
    fontWeight: 500,
    color: '#555',
  }

  const inputStyle: CSSProperties = {
    border: '1px solid rgba(0,0,0,0.15)',
    borderRadius: 8,
    padding: '7px 10px',
    fontSize: 13,
    color: '#1a1a1a',
    background: 'rgba(0,0,0,0.03)',
    outline: 'none',
  }

  const rowStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  }

  const actionsStyle: CSSProperties = {
    display: 'flex',
    gap: 8,
    justifyContent: 'flex-end',
    marginTop: 4,
  }

  const btnBase: CSSProperties = {
    padding: '7px 18px',
    borderRadius: 8,
    border: 'none',
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: 500,
  }

  const saveBtnStyle: CSSProperties = {
    ...btnBase,
    background: '#3060c0',
    color: '#fff',
  }

  const cancelBtnStyle: CSSProperties = {
    ...btnBase,
    background: 'rgba(0,0,0,0.07)',
    color: '#444',
  }

  const toggleStyle: CSSProperties = {
    width: 36,
    height: 20,
    borderRadius: 10,
    background: proactiveEnabled ? '#3060c0' : '#ccc',
    cursor: 'pointer',
    position: 'relative',
    border: 'none',
    transition: 'background 0.2s',
    flexShrink: 0,
  }

  const toggleDotStyle: CSSProperties = {
    position: 'absolute',
    top: 2,
    left: proactiveEnabled ? 18 : 2,
    width: 16,
    height: 16,
    borderRadius: '50%',
    background: '#fff',
    transition: 'left 0.2s',
    boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
  }

  return (
    <div style={overlayStyle} onMouseDown={onClose}>
      <div style={panelStyle} onMouseDown={(e) => e.stopPropagation()}>
        <div style={headerStyle}>
          <span style={titleStyle}>Settings</span>
          <button style={closeButtonStyle} onClick={onClose}>×</button>
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Gateway URL</label>
          <input
            style={inputStyle}
            type="text"
            value={gatewayUrl}
            onChange={(e) => setGatewayUrl(e.target.value)}
            placeholder="ws://localhost:8080"
          />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Gateway Token</label>
          <input
            style={inputStyle}
            type="password"
            value={gatewayToken}
            onChange={(e) => setGatewayToken(e.target.value)}
            placeholder="token"
          />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Bubble auto-dismiss (seconds)</label>
          <input
            style={inputStyle}
            type="number"
            min={1}
            max={60}
            value={bubbleTimeout}
            onChange={(e) => setBubbleTimeout(Number(e.target.value))}
          />
        </div>

        <div style={rowStyle}>
          <span style={labelStyle}>Proactive dialogue</span>
          <button
            style={toggleStyle}
            onClick={() => setProactiveEnabled(!proactiveEnabled)}
          >
            <span style={toggleDotStyle} />
          </button>
        </div>

        {proactiveEnabled && (
          <div style={fieldStyle}>
            <label style={labelStyle}>Proactive interval (minutes)</label>
            <input
              style={inputStyle}
              type="number"
              min={1}
              max={1440}
              value={proactiveInterval}
              onChange={(e) => setProactiveInterval(Number(e.target.value))}
            />
          </div>
        )}

        <div style={actionsStyle}>
          <button style={cancelBtnStyle} onClick={onClose}>Cancel</button>
          <button style={saveBtnStyle} onClick={handleSave}>Save</button>
        </div>
      </div>
    </div>
  )
}
