import { useState, useEffect, useCallback } from 'react'
import { getCurrentWindow, LogicalSize } from '@tauri-apps/api/window'
import { Ghost } from './components/Ghost'
import { Bubble } from './components/Bubble'
import { ChatInput } from './components/ChatInput'
import { ContextMenu } from './components/ContextMenu'
import { SkinPicker } from './components/SkinPicker'
import { SettingsPanel } from './components/SettingsPanel'
import { useOpenClaw } from './hooks/useOpenClaw'
import { useBubble } from './hooks/useBubble'
import { useSettings } from './hooks/useSettings'
import { useSkin } from './hooks/useSkin'

// Force WebKit to repaint transparent regions after overlay dismissal
// Opacity tricks don't work with WEBKIT_DISABLE_COMPOSITING_MODE=1;
// need to trigger a real window resize to force compositor redraw
async function forceRepaint() {
  const win = getCurrentWindow()
  const size = await win.innerSize()
  await win.setSize(new LogicalSize(size.width, size.height + 1))
  requestAnimationFrame(async () => {
    await win.setSize(new LogicalSize(size.width, size.height))
  })
}

export default function App() {
  const { settings, updateSettings } = useSettings()
  const { currentSkin, skins, switchSkin, getExpressionUrl } = useSkin()
  const {
    sendMessage,
    connectionStatus,
    currentResponse,
    currentExpression,
    chatState,
  } = useOpenClaw()

  const bubble = useBubble({ timeoutMs: settings.bubble_timeout_ms })

  const [chatOpen, setChatOpen] = useState(false)
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null)
  const [skinPickerOpen, setSkinPickerOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)

  // Ghost window position for layout
  const [ghostRect, setGhostRect] = useState({ x: 0, y: 0, width: 200 })

  // DEBUG: global event listener to check if webview receives mouse events
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      console.log(`[GLOBAL] ${e.type} button:${e.button} target:${(e.target as HTMLElement)?.tagName}`)
    }
    window.addEventListener('mousedown', handler)
    window.addEventListener('mouseup', handler)
    window.addEventListener('click', handler)
    window.addEventListener('auxclick', handler)
    window.addEventListener('contextmenu', handler)
    return () => {
      window.removeEventListener('mousedown', handler)
      window.removeEventListener('mouseup', handler)
      window.removeEventListener('click', handler)
      window.removeEventListener('auxclick', handler)
      window.removeEventListener('contextmenu', handler)
    }
  }, [])

  useEffect(() => {
    async function fetchPos() {
      const win = getCurrentWindow()
      const pos = await win.outerPosition()
      const size = await win.outerSize()
      setGhostRect({ x: pos.x, y: pos.y, width: size.width })
    }
    fetchPos()
  }, [])

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
    setContextMenu(null)
    setChatOpen((prev) => !prev)
  }, [])

  const handleMiddleClick = useCallback(() => {
    // TODO: "poking" interaction — trigger a reaction from the character
    console.log('poke!')
  }, [])

  const handleRightClick = useCallback((x: number, y: number) => {
    setChatOpen(false)
    setContextMenu({ x, y })
  }, [])

  const handleSend = useCallback((text: string) => {
    sendMessage(text)
    setChatOpen(false)
  }, [sendMessage])

  const handleTellMeMore = useCallback(() => {
    sendMessage('Tell me more')
    bubble.dismiss()
  }, [sendMessage, bubble])

  const handleSkinSelect = useCallback(async (id: string) => {
    await switchSkin(id)
    await updateSettings({ current_skin_id: id })
    setSkinPickerOpen(false)
  }, [switchSkin, updateSettings])

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

      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          onClose={() => { setContextMenu(null); forceRepaint() }}
          onChangeSkin={() => setSkinPickerOpen(true)}
          onSettings={() => setSettingsOpen(true)}
        />
      )}

      {skinPickerOpen && (
        <SkinPicker
          skins={skins}
          currentSkinId={currentSkin?.id ?? ''}
          onSelect={handleSkinSelect}
          onClose={() => { setSkinPickerOpen(false); forceRepaint() }}
        />
      )}

      {settingsOpen && (
        <SettingsPanel
          settings={settings}
          onSave={updateSettings}
          onClose={() => { setSettingsOpen(false); forceRepaint() }}
        />
      )}
    </>
  )
}
