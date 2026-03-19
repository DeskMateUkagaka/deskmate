import { useState, useEffect, useCallback, useRef } from 'react'
import { getCurrentWindow, getAllWindows, LogicalPosition, LogicalSize } from '@tauri-apps/api/window'
import { invoke } from '@tauri-apps/api/core'
import { listen, emit } from '@tauri-apps/api/event'
import { Menu, MenuItem, PredefinedMenuItem } from '@tauri-apps/api/menu'
import { moveWindow, getWindowPosition } from './lib/moveWindow'
import { calcWindowPosition, calcAnchor, type Origin, type ScreenMargins } from './lib/windowPosition'
import { Ghost, type ImageBounds } from './components/Ghost'
import type { BubbleTheme } from './types'
import { useOpenClaw } from './hooks/useOpenClaw'
import type { BubbleItem } from './hooks/useBubble'
import { useBubble } from './hooks/useBubble'
import { useSettings } from './hooks/useSettings'
import { useSkin } from './hooks/useSkin'
import { debugLog } from './lib/debugLog'

const FULL_BUBBLE_WINDOW_WIDTH = 648

interface BubbleWindowData {
  items: BubbleItem[]
  isVisible: boolean
  timeoutMs: number
  bubbleTheme: BubbleTheme | null
  contentOffsetX: number
  contentOffsetY: number
  origin: Origin
}

async function savePositionAndExit() {
  try {
    const win = getCurrentWindow()
    const pos = await getWindowPosition(win)
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
    debugLog(`[showPopup] ${label} at (${x}, ${y})`)
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
  const { currentSkin, skins, switchSkin, getEmotionUrl, reloadSkins } = useSkin()
  const {
    sendMessage,
    connectionStatus,
    currentResponse,
    currentEmotion,
    resetEmotion,
    chatState,
  } = useOpenClaw()

  const bubble = useBubble({ timeoutMs: settings.bubble_timeout_ms, onDismiss: resetEmotion })

  // Track window position on screen + monitor size for edge clamping
  // Use both state (for re-renders) and ref (for always-fresh reads in callbacks)
  const [windowPos, setWindowPos] = useState({ x: 0, y: 0 })
  const windowPosRef = useRef(windowPos)
  const [screenSize, setScreenSize] = useState({ width: window.screen.width, height: window.screen.height })

  useEffect(() => {
    // Screen size from Web API — no Tauri permission needed
    setScreenSize({ width: window.screen.width, height: window.screen.height })
  }, [])

  // Ghost reports its position on load and after drag via onPositionChange
  const handlePositionChange = useCallback((pos: { x: number; y: number }) => {
    windowPosRef.current = pos
    setWindowPos(pos)
  }, [])

  const [imageBounds, setImageBounds] = useState<ImageBounds | null>(null)
  const chatInputOpenRef = useRef(false)
  const fullBubbleHeight = screenSize.height - settings.popup_margin_top - settings.popup_margin_bottom
  const [bubbleWindowSize, setBubbleWindowSize] = useState({ width: FULL_BUBBLE_WINDOW_WIDTH, height: fullBubbleHeight })
  // Anchor point for input window positioning — set once when opened, reused on resize
  const inputAnchorRef = useRef({ centerX: 0, centerY: 0 })

  // Query fresh ghost position directly from compositor — avoids stale state
  const getGhostPos = useCallback(async () => {
    const ghostWin = getCurrentWindow()
    return await getWindowPosition(ghostWin)
  }, [])

  // Show the chat-input popup window, positioned above the ghost
  const showChatInput = useCallback(async () => {
    const win = await getWindowByLabel('chat-input')
    if (!win) return
    chatInputOpenRef.current = true

    // Query fresh ghost position from compositor to avoid stale state
    const ghostPos = await getGhostPos()

    // Compute screen position above the ghost image
    const p = currentSkin?.input_placement ?? { x: 0, y: -10, origin: 'center' as const }
    const inputWidth = 280
    const inputHeight = 44

    // Send max dimensions from skin manifest to the input window, capped by screen margins
    const maxWidth = Math.min(
      currentSkin?.input_theme?.max_width ?? 640,
      screenSize.width - settings.popup_margin_left - settings.popup_margin_right,
    )
    const maxHeight = Math.min(
      currentSkin?.input_theme?.max_height ?? 480,
      screenSize.height - settings.popup_margin_top - settings.popup_margin_bottom,
    )
    await emit('input-config', { maxWidth, maxHeight })

    // Reset to initial small size (will auto-grow as user types)
    await win.setSize(new LogicalSize(inputWidth, inputHeight))
    // GTK may enforce a minimum window size — query actual size for positioning
    // outerSize() returns physical pixels; convert to logical for Sway layout coords
    const actualSize = await win.outerSize()
    const scaleFactor = await win.scaleFactor()
    const actualWidth = actualSize.width / scaleFactor
    const actualHeight = actualSize.height / scaleFactor

    const anchor = calcAnchor(ghostPos, imageBounds, p)

    // Store anchor for reposition on resize
    inputAnchorRef.current = { centerX: anchor.x, centerY: anchor.y }

    debugLog(`[showChatInput] ghostPos=(${ghostPos.x}, ${ghostPos.y}) imageBounds=${JSON.stringify(imageBounds)} placement=${JSON.stringify(p)} anchor=(${anchor.x}, ${anchor.y}) actualSize=${actualWidth}x${actualHeight}`)

    const margins: ScreenMargins = {
      top: settings.popup_margin_top,
      bottom: settings.popup_margin_bottom,
      left: settings.popup_margin_left,
      right: settings.popup_margin_right,
    }
    // Input uses top-center origin: horizontally centered on anchor,
    // top edge at anchor Y (input grows downward as the user types)
    const { screenX, screenY } = calcWindowPosition(
      anchor.x, anchor.y, actualWidth, actualHeight, 'top-center',
      screenSize.width, screenSize.height, margins,
    )
    // Must show before moveWindow on Sway — hidden windows aren't in the
    // compositor tree so swaymsg can't target them.
    await win.show()
    await moveWindow(win, screenX, screenY)
    await win.setFocus()
  }, [imageBounds, windowPos, screenSize, currentSkin])

  // Reposition input window when it resizes (auto-grow), clamping to screen margins.
  // On Sway, debounce to once per second to avoid visible jumping from slow IPC.
  useEffect(() => {
    let unlisten: (() => void) | undefined
    let debounceTimer: ReturnType<typeof setTimeout> | null = null
    let compositorIpc = false

    invoke<boolean>('uses_compositor_ipc').then((v) => { compositorIpc = v })

    const reposition = async () => {
      const win = await getWindowByLabel('chat-input')
      if (!win) return

      // Reuse the anchor computed when the input was first shown — avoids
      // re-querying ghost position via slow compositor IPC and ensures
      // the same coordinate system as the initial placement.
      const { centerX, centerY } = inputAnchorRef.current

      // Query actual window size (GTK may enforce minimum)
      const actualSize = await win.outerSize()
      const scaleFactor = await win.scaleFactor()
      const actualWidth = actualSize.width / scaleFactor
      const actualHeight = actualSize.height / scaleFactor

      const margins: ScreenMargins = {
        top: settings.popup_margin_top,
        bottom: settings.popup_margin_bottom,
        left: settings.popup_margin_left,
        right: settings.popup_margin_right,
      }
      const { screenX, screenY } = calcWindowPosition(
        centerX, centerY, actualWidth, actualHeight, 'top-center',
        screenSize.width, screenSize.height, margins,
      )
      await moveWindow(win, screenX, screenY)
    }

    listen<{ width: number; height: number }>('input-resized', () => {
      if (compositorIpc) {
        // Sway: trailing debounce — reposition once, 1s after last resize
        if (debounceTimer) clearTimeout(debounceTimer)
        debounceTimer = setTimeout(() => {
          debounceTimer = null
          reposition()
        }, 1000)
      } else {
        reposition()
      }
    }).then((fn) => { unlisten = fn })

    return () => {
      unlisten?.()
      if (debounceTimer) clearTimeout(debounceTimer)
    }
  }, [screenSize, settings])

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
      const u4 = await listen<{ action: string; id?: string }>('bubble-action', (event) => {
        if (cancelled) return
        switch (event.payload.action) {
          case 'dismiss': bubble.dismiss(event.payload.id); break
          case 'pin': bubble.pin(event.payload.id); break
        }
      })
      if (cancelled) { u4(); return }
      unlisten.push(u4)

      const u5 = await listen<{ key: string }>('bubble-pass-through-key', (event) => {
        if (cancelled) return
        document.dispatchEvent(new KeyboardEvent('keydown', {
          key: event.payload.key,
          bubbles: true,
          cancelable: true,
        }))
      })
      if (cancelled) { u5(); return }
      unlisten.push(u5)
    }

    setup()

    return () => {
      cancelled = true
      unlisten.forEach((fn) => fn())
    }
  }, [reloadSettings, reloadSkins, updateSettings, sendMessage, bubble, showChatInput])

  useEffect(() => {
    let unlisten: (() => void) | undefined

    listen<{ width: number; height: number }>('bubble-content-sized', (event) => {
      setBubbleWindowSize({
        width: Math.max(1, Math.ceil(event.payload.width)),
        height: Math.max(1, Math.ceil(event.payload.height)),
      })
    }).then((fn) => { unlisten = fn })

    return () => unlisten?.()
  }, [])

  useEffect(() => {
    if (!bubble.isVisible || bubble.isStreaming) {
      setBubbleWindowSize({ width: FULL_BUBBLE_WINDOW_WIDTH, height: fullBubbleHeight })
    }
  }, [bubble.isVisible, bubble.isStreaming])

  // Broadcast connection status to popup windows
  useEffect(() => {
    emit('connection-status', connectionStatus)
  }, [connectionStatus])

  // Position and update the bubble popup window
  useEffect(() => {
    const origin = currentSkin?.bubble_placement?.origin ?? 'center'
    const emitBubbleUpdate = (contentOffsetX = 0, contentOffsetY = 0) =>
      emit<BubbleWindowData>('bubble-update', {
        items: bubble.items,
        isVisible: bubble.isVisible,
        timeoutMs: bubble.timeoutMs,
        bubbleTheme: currentSkin?.bubble_theme ?? null,
        contentOffsetX,
        contentOffsetY,
        origin,
      })

    if (bubble.isVisible) {
      ;(async () => {
        const win = await getWindowByLabel('bubble')
        if (!win) return
        await win.setSize(new LogicalSize(bubbleWindowSize.width, bubbleWindowSize.height))
        const actualSize = await win.outerSize()
        const scaleFactor = await win.scaleFactor()
        const actualWidth = actualSize.width / scaleFactor
        const actualHeight = actualSize.height / scaleFactor
        const ghostPos = await getGhostPos()
        const p = currentSkin?.bubble_placement ?? { x: 0, y: -20, origin: 'center' as const }

        const anchor = calcAnchor(ghostPos, imageBounds, p)
        const margins: ScreenMargins = {
          top: settings.popup_margin_top,
          bottom: settings.popup_margin_bottom,
          left: settings.popup_margin_left,
          right: settings.popup_margin_right,
        }
        const { screenX, screenY, offsetX, offsetY } = calcWindowPosition(
          anchor.x, anchor.y, actualWidth, actualHeight, origin as Origin,
          screenSize.width, screenSize.height, margins,
        )

        // When clamping shifts the window, pass the offset so BubbleWindow can
        // counter-shift its content to stay aligned with the ghost.
        emitBubbleUpdate(offsetX, offsetY)

        // Must show before moveWindow on Sway — hidden windows aren't in the
        // compositor tree so swaymsg can't target them.
        await win.show()
        await moveWindow(win, screenX, screenY)
      })()
    } else {
      emitBubbleUpdate()
      hidePopup('bubble')
    }
  }, [bubble.items, bubble.isStreaming, bubble.isVisible, bubble.timeoutMs, bubbleWindowSize, imageBounds, screenSize, currentSkin, settings, getGhostPos])

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
    debugLog('poke!')
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
    const reloadConfigItem = await MenuItem.new({
      text: 'Reload Settings',
      action: () => { reloadSkins(); reloadSettings() },
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
      items: [toggleItem, separator0, changeSkin, reloadConfigItem, buySkins, separator, settings, separator2, exitItem],
    })
    await menu.popup(new LogicalPosition(clientX, clientY), win)
  }, [reloadSkins, reloadSettings])

  const emotionUrl = getEmotionUrl(currentEmotion)

  return (
    <Ghost
      emotionOverride={emotionUrl || undefined}
      ghostHeightPixels={settings.ghost_height_pixels}
      onLeftClick={handleGhostClick}
      onMiddleClick={handleMiddleClick}
      onRightClick={handleRightClick}
      onImageBounds={setImageBounds}
      onPositionChange={handlePositionChange}
    />
  )
}
