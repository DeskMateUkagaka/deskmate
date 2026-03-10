import { useState, useEffect, useRef, useCallback } from 'react'

export type BubbleState = 'hidden' | 'streaming' | 'visible' | 'dismissing'

const PREVIEW_LENGTH = 200

import { getCurrentWindow, PhysicalSize, PhysicalPosition } from '@tauri-apps/api/window'

/**
 * Force WebKitGTK to repaint by resizing the window, then restoring
 * both size and position (Sway may move the window on resize).
 * Uses physical pixels to avoid logical/physical mismatch on HiDPI Wayland.
 */
async function nudgeWindowRepaint() {
  const win = getCurrentWindow()
  const pos = await win.outerPosition()
  const size = await win.outerSize()
  await win.setSize(new PhysicalSize(size.width + 1, size.height + 1))
  await new Promise(r => requestAnimationFrame(r))
  await win.setSize(new PhysicalSize(size.width, size.height))
  await win.setPosition(new PhysicalPosition(pos.x, pos.y))
}

interface UseBubbleOptions {
  timeoutMs?: number
}

export function useBubble(options: UseBubbleOptions = {}) {
  const { timeoutMs = 8000 } = options

  const [bubbleState, setBubbleState] = useState<BubbleState>('hidden')
  const [text, setText] = useState('')
  const [isExpanded, setIsExpanded] = useState(false)
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearDismissTimer = useCallback(() => {
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = null
    }
  }, [])

  const startDismissTimer = useCallback(() => {
    clearDismissTimer()
    dismissTimerRef.current = setTimeout(() => {
      setBubbleState('hidden')
      nudgeWindowRepaint()
    }, timeoutMs)
  }, [timeoutMs, clearDismissTimer])

  // Called when streaming starts
  const startStreaming = useCallback((initialText: string) => {
    clearDismissTimer()
    setText(initialText)
    setIsExpanded(false)
    setBubbleState('streaming')
  }, [clearDismissTimer])

  // Called with each new chunk
  const updateText = useCallback((newText: string) => {
    setText(newText)
  }, [])

  // Called when response is final
  const finalize = useCallback(() => {
    setBubbleState('visible')
    startDismissTimer()
  }, [startDismissTimer])

  const dismiss = useCallback(() => {
    clearDismissTimer()
    setBubbleState('hidden')
    nudgeWindowRepaint()
  }, [clearDismissTimer])

  const expand = useCallback(() => {
    setIsExpanded(true)
    // User wants to read — clear dismiss timer, don't auto-hide
    clearDismissTimer()
  }, [clearDismissTimer])

  const resetTimeout = useCallback(() => {
    if (bubbleState === 'visible') {
      startDismissTimer()
    }
  }, [bubbleState, startDismissTimer])

  useEffect(() => {
    return () => clearDismissTimer()
  }, [clearDismissTimer])

  const isVisible = bubbleState !== 'hidden'
  const isStreaming = bubbleState === 'streaming'
  const displayText = isExpanded ? text : (text.length > PREVIEW_LENGTH ? text.slice(0, PREVIEW_LENGTH) + '...' : text)
  const isTruncated = text.length > PREVIEW_LENGTH && !isExpanded

  return {
    isVisible,
    text: displayText,
    fullText: text,
    isTruncated,
    isExpanded,
    isStreaming,
    bubbleState,
    startStreaming,
    updateText,
    finalize,
    expand,
    dismiss,
    resetTimeout,
  }
}
