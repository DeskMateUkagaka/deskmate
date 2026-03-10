import { useState, useEffect, useCallback } from 'react'
import { getCurrentWindow, getAllWindows, LogicalPosition } from '@tauri-apps/api/window'
import { emit, listen } from '@tauri-apps/api/event'
import { Menu, MenuItem, PredefinedMenuItem } from '@tauri-apps/api/menu'
import { Ghost } from './components/Ghost'
import { Bubble } from './components/Bubble'
import { useOpenClaw } from './hooks/useOpenClaw'
import { useBubble } from './hooks/useBubble'
import { useSettings } from './hooks/useSettings'
import { useSkin } from './hooks/useSkin'

async function getWindowByLabel(label: string) {
  const all = await getAllWindows()
  return all.find((w) => w.label === label) ?? null
}

async function showPopup(label: string, x?: number, y?: number) {
  const win = await getWindowByLabel(label)
  if (!win) return
  await win.show()
  if (x !== undefined && y !== undefined) {
    // Try both position types for debugging
    console.log(`[showPopup] ${label} at (${x}, ${y})`)
    await win.setPosition(new LogicalPosition(x, y))
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

  // Window viewport size for overlay positioning
  const [viewportSize, setViewportSize] = useState({ width: 400, height: 600 })

  useEffect(() => {
    const update = () => setViewportSize({ width: window.innerWidth, height: window.innerHeight })
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  // Broadcast connection status to chat-input window
  useEffect(() => {
    emit('connection-status', connectionStatus)
  }, [connectionStatus])

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

      const u3 = await listen<{ text: string }>('chat-send', (event) => {
        if (!cancelled) {
          console.log('[App] chat-send event received:', event.payload)
          sendMessage(event.payload.text)
        }
      })
      if (cancelled) { u3(); return }
      unlisten.push(u3)
    }

    setup()

    return () => {
      cancelled = true
      unlisten.forEach((fn) => fn())
    }
  }, [reloadSettings, reloadSkins, updateSettings, sendMessage])

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

  const handleGhostClick = useCallback(async () => {
    const chatWin = await getWindowByLabel('chat-input')
    if (!chatWin) return
    const isVisible = await chatWin.isVisible()
    if (isVisible) {
      await chatWin.hide()
    } else {
      // Position chat-input window above the ghost window
      const mainWin = getCurrentWindow()
      const pos = await mainWin.outerPosition()
      const size = await mainWin.outerSize()
      await chatWin.setPosition(new LogicalPosition(
        pos.x + (size.width - 280) / 2,
        pos.y - 50
      ))
      await chatWin.show()
      await chatWin.setFocus()
    }
  }, [])

  const handleMiddleClick = useCallback(() => {
    console.log('poke!')
  }, [])

  const handleRightClick = useCallback(async (clientX: number, clientY: number) => {
    hidePopup('chat-input')
    const win = getCurrentWindow()
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
    const menu = await Menu.new({
      items: [changeSkin, buySkins, separator, settings],
    })
    await menu.popup(new LogicalPosition(clientX, clientY), win)
  }, [])

  const handleTellMeMore = useCallback(() => {
    sendMessage('Tell me more')
    bubble.dismiss()
  }, [sendMessage, bubble])

  const expressionUrl = getExpressionUrl(currentExpression)

  return (
    <>
      <Ghost
        expressionOverride={expressionUrl || undefined}
        onLeftClick={handleGhostClick}
        onMiddleClick={handleMiddleClick}
        onRightClick={handleRightClick}
      />

      <Bubble
        text={bubble.text}
        isTruncated={bubble.isTruncated}
        isStreaming={bubble.isStreaming}
        isVisible={bubble.isVisible}
        bubbleState={bubble.bubbleState}
        viewportWidth={viewportSize.width}
        onExpand={bubble.expand}
        onDismiss={bubble.dismiss}
        onTellMeMore={handleTellMeMore}
      />

    </>
  )
}
