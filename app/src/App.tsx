import { useState, useEffect, useCallback } from 'react'
import { getCurrentWindow, getAllWindows, LogicalPosition } from '@tauri-apps/api/window'
import { invoke } from '@tauri-apps/api/core'
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

  // Inline chat input state
  const [chatInputOpen, setChatInputOpen] = useState(false)

  // Enter key opens chat input
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'q' && e.ctrlKey) {
        invoke('exit_app')
        return
      }
      if (e.key === 'Enter' && !chatInputOpen) {
        setChatInputOpen(true)
      }
    }
    document.addEventListener('keyup', handleKey)
    return () => document.removeEventListener('keyup', handleKey)
  }, [chatInputOpen])
  const [ghostImageBottom, setGhostImageBottom] = useState<number | null>(null)

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
    }

    setup()

    return () => {
      cancelled = true
      unlisten.forEach((fn) => fn())
    }
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
    setChatInputOpen(prev => !prev)
  }, [])

  const handleMiddleClick = useCallback(() => {
    console.log('poke!')
  }, [])

  const handleRightClick = useCallback(async (clientX: number, clientY: number) => {
    setChatInputOpen(false)
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
    const separator2 = await PredefinedMenuItem.new({ item: 'Separator' })
    const exitItem = await MenuItem.new({
      text: 'Exit',
      action: () => invoke('exit_app'),
    })
    const menu = await Menu.new({
      items: [changeSkin, buySkins, separator, settings, separator2, exitItem],
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
        onImageBounds={setGhostImageBottom}
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

      <ChatInput
        isOpen={chatInputOpen}
        connectionStatus={connectionStatus}
        viewportWidth={viewportSize.width}
        imageBottom={ghostImageBottom}
        onSend={sendMessage}
        onClose={() => setChatInputOpen(false)}
      />
    </>
  )
}
