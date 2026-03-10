import { useState, useEffect, useCallback } from 'react'
import { getCurrentWindow, getAllWindows, LogicalPosition } from '@tauri-apps/api/window'
import { listen } from '@tauri-apps/api/event'
import { Menu, MenuItem, PredefinedMenuItem } from '@tauri-apps/api/menu'
import { Ghost } from './components/Ghost'
import { Bubble } from './components/Bubble'
import { ChatInput } from './components/ChatInput'
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

  const [chatOpen, setChatOpen] = useState(false)

  // Ghost window position for layout
  const [ghostRect, setGhostRect] = useState({ x: 0, y: 0, width: 200 })

  useEffect(() => {
    async function fetchPos() {
      const win = getCurrentWindow()
      const pos = await win.outerPosition()
      const size = await win.outerSize()
      setGhostRect({ x: pos.x, y: pos.y, width: size.width })
    }
    fetchPos()
  }, [])

  // Listen for events from popup windows
  useEffect(() => {
    const unlisten: Array<() => void> = []

    listen('settings-saved', () => {
      reloadSettings()
    }).then((fn) => unlisten.push(fn))

    listen<{ id: string }>('skin-selected', (event) => {
      const { id } = event.payload
      updateSettings({ current_skin_id: id })
      reloadSkins()
    }).then((fn) => unlisten.push(fn))

    return () => unlisten.forEach((fn) => fn())
  }, [reloadSettings, reloadSkins, updateSettings])

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
      bubble.finalize()
    }
    if (chatState === 'error') {
      bubble.finalize()
    }
  }, [chatState]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleGhostClick = useCallback(() => {
    setChatOpen((prev) => !prev)
  }, [])

  const handleMiddleClick = useCallback(() => {
    console.log('poke!')
  }, [])

  const handleRightClick = useCallback(async (clientX: number, clientY: number) => {
    setChatOpen(false)
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

  const handleSend = useCallback((text: string) => {
    sendMessage(text)
    setChatOpen(false)
  }, [sendMessage])

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
        ghostX={ghostRect.x}
        ghostWidth={ghostRect.width}
        screenWidth={window.screen.width}
        onExpand={bubble.expand}
        onDismiss={bubble.dismiss}
        onTellMeMore={handleTellMeMore}
      />

      <ChatInput
        isOpen={chatOpen}
        connectionStatus={connectionStatus}
        ghostX={ghostRect.x}
        ghostY={ghostRect.y}
        ghostWidth={ghostRect.width}
        onSend={handleSend}
        onClose={() => setChatOpen(false)}
      />
    </>
  )
}
