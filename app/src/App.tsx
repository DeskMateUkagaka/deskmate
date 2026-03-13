import { useState, useEffect, useCallback, useRef } from 'react'
import { getCurrentWindow, getAllWindows, LogicalPosition, LogicalSize } from '@tauri-apps/api/window'
import { invoke } from '@tauri-apps/api/core'
import { listen, emit } from '@tauri-apps/api/event'
import { Menu, MenuItem, PredefinedMenuItem } from '@tauri-apps/api/menu'
import { moveWindow } from './lib/moveWindow'
import { Ghost, type ImageBounds } from './components/Ghost'
import { useOpenClaw } from './hooks/useOpenClaw'
import { useBubble } from './hooks/useBubble'
import { useSettings } from './hooks/useSettings'
import { useSkin } from './hooks/useSkin'

async function savePositionAndExit() {
  try {
    const win = getCurrentWindow()
    const pos = await win.outerPosition()
    await invoke('set_ghost_position', { x: pos.x, y: pos.y })
  } catch (e) {
    console.error('Failed to save position:', e)
  }
  await invoke('exit_app')
}

async function getWindowByLabel(label: string) {
  const all = await getAllWindows()
  return all.find((w) => w.label === label) ?? null
}

async function showPopup(label: string, x?: number, y?: number) {
  const win = await getWindowByLabel(label)
  if (!win) return
  await win.show()
  if (x !== undefined && y !== undefined) {
    console.log(`[showPopup] ${label} at (${x}, ${y})`)
    await moveWindow(win, x, y)
  }
  await win.setFocus()
}

async function hidePopup(label: string) {
  const win = await getWindowByLabel(label)
  if (!win) return
  await win.hide()
}

export default function App() {
  const { settings, updateSettings, reloadSettings } = useSettings()
  const { currentSkin, skins, switchSkin, getExpressionUrl, reloadSkins } = useSkin()
  const {
    sendMessage,
    connectionStatus,
    currentResponse,
    currentExpression,
    chatState,
  } = useOpenClaw()

  const bubble = useBubble({ timeoutMs: settings.bubble_timeout_ms })

  // Track window position on screen + monitor size for edge clamping
  const [windowPos, setWindowPos] = useState({ x: 0, y: 0 })
  const [screenSize, setScreenSize] = useState({ width: window.screen.width, height: window.screen.height })

  useEffect(() => {
    const win = getCurrentWindow()
    let cancelled = false

    // Screen size from Web API — no Tauri permission needed
    setScreenSize({ width: window.screen.width, height: window.screen.height })

    // Get initial window position
    win.outerPosition()
      .then((pos) => { if (!cancelled) setWindowPos({ x: pos.x, y: pos.y }) })
      .catch(() => {})

    // Update window position on move
    let unlistenMove: (() => void) | null = null
    win.onMoved(() => {
      win.outerPosition()
        .then((pos) => {
          if (!cancelled) setWindowPos({ x: pos.x, y: pos.y })
        })
        .catch(() => {})
    }).then((fn) => { if (!cancelled) unlistenMove = fn; else fn() })
      .catch(() => {})

    return () => {
      cancelled = true
      unlistenMove?.()
    }
  }, [])

  const [imageBounds, setImageBounds] = useState<ImageBounds | null>(null)
  const chatInputOpenRef = useRef(false)

  // Show the chat-input popup window, positioned above the ghost
  const showChatInput = useCallback(async () => {
    const win = await getWindowByLabel('chat-input')
    if (!win) return
    chatInputOpenRef.current = true

    // Compute screen position above the ghost image
    const p = currentSkin?.input_placement ?? { x: 0, y: -10, margin_x: 10, margin_y: 10 }
    const inputWidth = 280
    const inputHeight = 44

    await win.setSize(new LogicalSize(inputWidth, inputHeight))
    // GTK may enforce a minimum window size — query actual size for positioning
    const actualSize = await win.outerSize()
    const actualWidth = actualSize.width
    const actualHeight = actualSize.height

    // Compute desired bottom edge of the input window
    let bottomEdgeY: number
    let centerX: number
    if (imageBounds) {
      centerX = windowPos.x + imageBounds.centerX + p.x
      bottomEdgeY = windowPos.y + imageBounds.top + p.y
    } else {
      centerX = windowPos.x + p.x
      bottomEdgeY = windowPos.y - 10 + p.y
    }

    // Position from the actual size (not the requested size)
    let screenX = centerX - actualWidth / 2
    let screenY = bottomEdgeY - actualHeight
    // Clamp to screen with margins
    screenX = Math.max(p.margin_x, Math.min(screenX, screenSize.width - actualWidth - p.margin_x))
    screenY = Math.max(p.margin_y, Math.min(screenY, screenSize.height - actualHeight - p.margin_y))
    await win.show()
    await moveWindow(win, screenX, screenY)
    await win.setFocus()
  }, [imageBounds, windowPos, screenSize, currentSkin])

  // Enter key opens chat input, Ctrl+Q exits
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'q' && e.ctrlKey) {
        savePositionAndExit()
        return
      }
      if (e.key === 'Enter') {
        showChatInput()
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [showChatInput])

  // Listen for events from popup windows
  useEffect(() => {
    let cancelled = false
    const unlisten: Array<() => void> = []

    async function setup() {
      const u1 = await listen('settings-saved', () => {
        if (!cancelled) reloadSettings()
      })
      if (cancelled) { u1(); return }
      unlisten.push(u1)

      const u2 = await listen<{ id: string }>('skin-selected', (event) => {
        if (!cancelled) {
          updateSettings({ current_skin_id: event.payload.id })
          reloadSkins()
        }
      })
      if (cancelled) { u2(); return }
      unlisten.push(u2)

      // Listen for chat messages from the popup chat-input window
      const u3 = await listen<{ text: string }>('chat-send', (event) => {
        if (!cancelled) {
          if (event.payload.text) sendMessage(event.payload.text)
          chatInputOpenRef.current = false
        }
      })
      if (cancelled) { u3(); return }
      unlisten.push(u3)

      // Listen for bubble actions from the popup bubble window
      const u4 = await listen<{ action: string }>('bubble-action', (event) => {
        if (cancelled) return
        switch (event.payload.action) {
          case 'dismiss': bubble.dismiss(); break
          case 'pin': bubble.pin(); break
          case 'tell-me-more': sendMessage('Tell me more'); bubble.dismiss(); break
        }
      })
      if (cancelled) { u4(); return }
      unlisten.push(u4)
    }

    setup()

    return () => {
      cancelled = true
      unlisten.forEach((fn) => fn())
    }
  }, [reloadSettings, reloadSkins, updateSettings, sendMessage, bubble])

  // Broadcast connection status to popup windows
  useEffect(() => {
    emit('connection-status', connectionStatus)
  }, [connectionStatus])

  // Position and update the bubble popup window
  useEffect(() => {
    emit('bubble-update', {
      text: bubble.text,
      isStreaming: bubble.isStreaming,
      isVisible: bubble.isVisible,
      isPinned: bubble.isPinned,
      timeoutMs: bubble.timeoutMs,
      finalizedAt: bubble.finalizedAt,
    })

    if (bubble.isVisible) {
      // Position the bubble window above the ghost
      ;(async () => {
        const win = await getWindowByLabel('bubble')
        if (!win) return
        const p = currentSkin?.bubble_placement ?? { x: 0, y: -20, margin_x: 10, margin_y: 10 }
        const bubbleWidth = 280
        const bubbleHeight = 200

        let screenX: number
        let screenY: number
        if (imageBounds) {
          screenX = windowPos.x + imageBounds.centerX + p.x - bubbleWidth / 2
          screenY = windowPos.y + imageBounds.top + p.y - bubbleHeight
        } else {
          screenX = windowPos.x - bubbleWidth / 2
          screenY = windowPos.y - bubbleHeight - 10
        }
        screenX = Math.max(p.margin_x, Math.min(screenX, screenSize.width - bubbleWidth - p.margin_x))
        screenY = Math.max(p.margin_y, Math.min(screenY, screenSize.height - bubbleHeight - p.margin_y))

        await moveWindow(win, screenX, screenY)
        await win.show()
      })()
    } else {
      hidePopup('bubble')
    }
  }, [bubble.text, bubble.isStreaming, bubble.isVisible, bubble.isPinned, bubble.finalizedAt, bubble.timeoutMs, imageBounds, windowPos, screenSize, currentSkin])

  // Wire streaming response into bubble
  useEffect(() => {
    if (chatState === 'sending' || chatState === 'streaming') {
      if (!bubble.isVisible || !bubble.isStreaming) {
        bubble.startStreaming(currentResponse)
      } else {
        bubble.updateText(currentResponse)
      }
    }
  }, [currentResponse, chatState]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (chatState === 'idle' && bubble.isStreaming) {
      // Update text one last time — the final event may have arrived with
      // chatState='idle' in the same render, so Effect 1 above skipped it.
      bubble.updateText(currentResponse)
      bubble.finalize()
    }
    if (chatState === 'error') {
      bubble.updateText(currentResponse)
      bubble.finalize()
    }
  }, [chatState, currentResponse]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleGhostClick = useCallback(() => {
    showChatInput()
  }, [showChatInput])

  const handleMiddleClick = useCallback(() => {
    console.log('poke!')
  }, [])

  const handleRightClick = useCallback(async (clientX: number, clientY: number) => {
    hidePopup('chat-input')
    chatInputOpenRef.current = false
    const win = getCurrentWindow()
    const toggleItem = await MenuItem.new({
      text: 'Show / Hide',
      action: () => {
        if (win.isVisible()) {
          win.hide()
        } else {
          win.show()
          win.setFocus()
        }
      },
    })
    const separator0 = await PredefinedMenuItem.new({ item: 'Separator' })
    const changeSkin = await MenuItem.new({
      text: 'Change Skin',
      action: () => showPopup('skin-picker'),
    })
    const buySkins = await MenuItem.new({
      text: 'Buy Skins',
      action: () => { /* TODO: open external URL */ },
    })
    const separator = await PredefinedMenuItem.new({ item: 'Separator' })
    const settings = await MenuItem.new({
      text: 'Settings',
      action: () => showPopup('settings'),
    })
    const separator2 = await PredefinedMenuItem.new({ item: 'Separator' })
    const exitItem = await MenuItem.new({
      text: 'Exit',
      action: () => savePositionAndExit(),
    })
    const menu = await Menu.new({
      items: [toggleItem, separator0, changeSkin, buySkins, separator, settings, separator2, exitItem],
    })
    await menu.popup(new LogicalPosition(clientX, clientY), win)
  }, [])

  const expressionUrl = getExpressionUrl(currentExpression)

  return (
    <Ghost
      expressionOverride={expressionUrl || undefined}
      ghostHeightPixels={settings.ghost_height_pixels}
      onLeftClick={handleGhostClick}
      onMiddleClick={handleMiddleClick}
      onRightClick={handleRightClick}
      onImageBounds={setImageBounds}
    />
  )
}
