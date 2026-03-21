import { useState, useEffect, useRef, useCallback, useMemo, type CSSProperties, type KeyboardEvent } from 'react'
import { emit, listen } from '@tauri-apps/api/event'
import { getCurrentWindow } from '@tauri-apps/api/window'
import { LogicalSize } from '@tauri-apps/api/window'
import type { ConnectionStatus } from '../hooks/useOpenClaw'
import type { SlashCommand } from '../types'

const STATUS_COLORS: Record<ConnectionStatus, string> = {
  connected: '#4caf50',
  connecting: '#ff9800',
  disconnected: '#9e9e9e',
  error: '#f44336',
}

const MIN_WIDTH = 280
const MIN_HEIGHT = 44
const DEFAULT_MAX_WIDTH = 640
const DEFAULT_MAX_HEIGHT = 480
const MAX_DROPDOWN_ITEMS = 8

interface InputConfig {
  maxWidth: number
  maxHeight: number
}

/** Find the slash trigger position and filter text from the current cursor position */
function findSlashTrigger(text: string, cursorPos: number): { triggerIndex: number; filterText: string } | null {
  // Search backwards from cursor for the last '/'
  for (let i = cursorPos - 1; i >= 0; i--) {
    const ch = text[i]
    if (ch === '/') {
      const partial = text.slice(i + 1, cursorPos)
      // If there's a space in the partial, it's not a command trigger
      if (partial.includes(' ')) return null
      return { triggerIndex: i, filterText: partial }
    }
    // Stop at whitespace — the '/' must be preceded by whitespace or be at position 0
    if (ch === ' ' || ch === '\n' || ch === '\t') return null
  }
  return null
}

export function ChatInputWindow() {
  const [value, setValue] = useState('')
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected')
  const [config, setConfig] = useState<InputConfig>({ maxWidth: DEFAULT_MAX_WIDTH, maxHeight: DEFAULT_MAX_HEIGHT })
  const [commands, setCommands] = useState<SlashCommand[]>([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [slashTrigger, setSlashTrigger] = useState<{ triggerIndex: number; filterText: string } | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const win = getCurrentWindow()

  // Filter commands based on the current slash trigger
  const filteredCommands = useMemo(() => {
    if (!slashTrigger || commands.length === 0) return []
    const prefix = '/' + slashTrigger.filterText.toLowerCase()
    return commands.filter(cmd => cmd.name.toLowerCase().startsWith(prefix))
  }, [commands, slashTrigger])

  const dropdownVisible = filteredCommands.length > 0

  // Reset selected index when filtered list changes
  useEffect(() => {
    setSelectedIndex(0)
  }, [filteredCommands.length])

  // Update slash trigger from current textarea state
  const updateSlashTrigger = useCallback(() => {
    const ta = textareaRef.current
    if (!ta) return
    const cursorPos = ta.selectionStart
    setSlashTrigger(findSlashTrigger(ta.value, cursorPos))
  }, [])

  // Focus textarea when window becomes visible
  useEffect(() => {
    let unlisten: (() => void) | undefined
    win.onFocusChanged(({ payload: focused }) => {
      if (focused) {
        textareaRef.current?.focus()
      } else if (!textareaRef.current?.value) {
        win.hide()
      }
    }).then((fn) => { unlisten = fn })
    setTimeout(() => textareaRef.current?.focus(), 50)
    return () => unlisten?.()
  }, [win])

  // Listen for connection status updates from main window
  useEffect(() => {
    let unlisten: (() => void) | undefined
    listen<ConnectionStatus>('connection-status', (event) => {
      setConnectionStatus(event.payload)
    }).then((fn) => { unlisten = fn })
    return () => unlisten?.()
  }, [])

  // Listen for input config from main window
  useEffect(() => {
    let unlisten: (() => void) | undefined
    listen<InputConfig>('input-config', (event) => {
      setConfig(event.payload)
    }).then((fn) => { unlisten = fn })
    return () => unlisten?.()
  }, [])

  // Listen for slash commands from main window
  useEffect(() => {
    let unlisten: (() => void) | undefined
    listen<SlashCommand[]>('slash-commands', (event) => {
      setCommands(event.payload)
    }).then((fn) => { unlisten = fn })
    return () => unlisten?.()
  }, [])

  // ESC to close (only when input is empty and dropdown not visible)
  useEffect(() => {
    const handleKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape' && !textareaRef.current?.value) win.hide()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [win])

  // Auto-resize window to fit textarea content + dropdown
  const resizeToFit = useCallback(async () => {
    const ta = textareaRef.current
    if (!ta) return

    // Reset height to measure scrollHeight accurately
    ta.style.height = '0px'
    const scrollH = ta.scrollHeight
    const contentHeight = Math.min(scrollH, config.maxHeight - 20) // 20 = padding
    ta.style.height = contentHeight + 'px'

    // Compute desired window size
    // Width: start at MIN_WIDTH, grow to maxWidth based on longest line
    const lines = ta.value.split('\n')
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    let longestLinePx = 0
    if (ctx) {
      ctx.font = '13px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif'
      for (const line of lines) {
        const w = ctx.measureText(line).width
        if (w > longestLinePx) longestLinePx = w
      }
    }
    // Add padding (12px left + 12px right + dot 8px + gap 6px + close btn ~20px + gap 6px = ~64px)
    const desiredWidth = Math.max(MIN_WIDTH, Math.min(longestLinePx + 64, config.maxWidth))
    // panel padding top/bottom 6+6=12, border 2, plus textarea height
    // Calculate dropdown height from item count rather than measuring DOM
    // (DOM measurement fails on first render when window is still too small)
    const dropdownItemCount = Math.min(filteredCommands.length, MAX_DROPDOWN_ITEMS)
    const dropdownHeight = dropdownItemCount > 0 ? dropdownItemCount * 32 + 2 : 0 // +2 for border
    const desiredHeight = Math.max(MIN_HEIGHT, contentHeight + 14 + dropdownHeight)
    const clampedHeight = Math.min(desiredHeight, config.maxHeight)

    const finalWidth = Math.ceil(desiredWidth)
    const finalHeight = Math.ceil(clampedHeight)
    await win.setSize(new LogicalSize(finalWidth, finalHeight))
    // Notify main window so it can reposition with margin clamping
    await emit('input-resized', { width: finalWidth, height: finalHeight })
  }, [win, config, filteredCommands.length])

  // Resize when value or dropdown visibility changes
  useEffect(() => {
    resizeToFit()
  }, [value, dropdownVisible, filteredCommands.length, resizeToFit])

  // Insert a command at the slash trigger position
  const insertCommand = useCallback((cmd: SlashCommand) => {
    if (!slashTrigger) return
    const before = value.slice(0, slashTrigger.triggerIndex)
    const after = value.slice(slashTrigger.triggerIndex + 1 + slashTrigger.filterText.length)
    const inserted = cmd.name + ' '
    const newValue = before + inserted + after
    setValue(newValue)
    setSlashTrigger(null)

    // Set cursor position after the inserted command
    requestAnimationFrame(() => {
      const ta = textareaRef.current
      if (ta) {
        const newPos = before.length + inserted.length
        ta.selectionStart = newPos
        ta.selectionEnd = newPos
        ta.focus()
      }
    })
  }, [value, slashTrigger])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // When dropdown is visible, handle navigation keys
    if (dropdownVisible) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex(i => (i + 1) % filteredCommands.length)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex(i => (i - 1 + filteredCommands.length) % filteredCommands.length)
        return
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault()
        insertCommand(filteredCommands[selectedIndex])
        return
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        setSlashTrigger(null)
        return
      }
    }

    // Default: Enter sends message
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (value.trim()) {
        emit('chat-send', { text: value.trim() })
        setValue('')
      }
      win.hide()
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value)
    // Update slash trigger after value changes
    requestAnimationFrame(() => updateSlashTrigger())
  }

  // Track cursor repositioning via click or arrow keys
  const handleSelect = () => {
    updateSlashTrigger()
  }

  const handleClose = () => win.hide()

  const outerStyle: CSSProperties = {
    width: '100vw',
    height: '100vh',
    background: 'transparent',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'stretch',
  }

  const panelStyle: CSSProperties = {
    background: '#fff',
    display: 'flex',
    alignItems: 'flex-start',
    gap: 6,
    padding: '6px 12px',
    width: '100%',
    borderRadius: dropdownVisible ? '12px 12px 0 0' : 12,
    border: '1px solid #d0d0d0',
    borderBottom: dropdownVisible ? '1px solid #e8e8e8' : '1px solid #d0d0d0',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
    boxSizing: 'border-box',
  }

  const textareaStyle: CSSProperties = {
    flex: 1,
    border: 'none',
    background: 'transparent',
    outline: 'none',
    fontSize: 13,
    color: '#1a1a1a',
    resize: 'none',
    lineHeight: '20px',
    padding: 0,
    margin: 0,
    fontFamily: 'inherit',
    overflow: 'auto',
  }

  const dotStyle: CSSProperties = {
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: STATUS_COLORS[connectionStatus],
    flexShrink: 0,
    marginTop: 6,
  }

  const closeBtnStyle: CSSProperties = {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    fontSize: 14,
    color: '#999',
    padding: '0 2px',
    lineHeight: 1,
    flexShrink: 0,
    marginTop: 2,
  }

  const dropdownStyle: CSSProperties = {
    background: '#fff',
    borderRadius: '0 0 12px 12px',
    border: '1px solid #d0d0d0',
    borderTop: 'none',
    maxHeight: MAX_DROPDOWN_ITEMS * 32,
    overflowY: 'auto',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
    boxSizing: 'border-box',
  }

  const getItemStyle = (isSelected: boolean): CSSProperties => ({
    padding: '6px 12px',
    cursor: 'pointer',
    background: isSelected ? '#f0f0f0' : 'transparent',
    display: 'flex',
    gap: 8,
    alignItems: 'baseline',
    fontSize: 13,
  })

  const cmdNameStyle: CSSProperties = {
    fontWeight: 600,
    color: '#1a1a1a',
    whiteSpace: 'nowrap',
  }

  const cmdDescStyle: CSSProperties = {
    color: '#888',
    fontSize: 12,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  }

  return (
    <div style={outerStyle}>
      <div style={panelStyle}>
        <span style={dotStyle} title={connectionStatus} />
        <textarea
          ref={textareaRef}
          style={textareaStyle}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onSelect={handleSelect}
          placeholder="Say something... (Shift+Enter for newline)"
          rows={1}
        />
        <button style={closeBtnStyle} onClick={handleClose} title="Close">✕</button>
      </div>
      {dropdownVisible && (
        <div ref={dropdownRef} style={dropdownStyle}>
          {filteredCommands.map((cmd, i) => (
            <div
              key={cmd.name}
              style={getItemStyle(i === selectedIndex)}
              onMouseEnter={() => setSelectedIndex(i)}
              onMouseDown={(e) => {
                e.preventDefault() // prevent textarea blur
                insertCommand(cmd)
              }}
            >
              <span style={cmdNameStyle}>{cmd.name}</span>
              <span style={cmdDescStyle}>{cmd.description}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
