import { useState, useEffect, useRef, useCallback } from 'react'

export type BubbleState = 'hidden' | 'streaming' | 'visible' | 'dismissing'

import { getCurrentWindow, PhysicalSize, PhysicalPosition } from '@tauri-apps/api/window'

/**
 * Force WebKitGTK to repaint by resizing the window, then restoring
 * both size and position (tiling WMs may move the window on resize).
 * Uses physical pixels to avoid logical/physical mismatch on HiDPI Wayland.
 *
 * Double rAF ensures one full frame has been composited before restoring —
 * a single rAF fires before the paint, which isn't enough on X11 (i3).
 */
async function nudgeWindowRepaint() {
  const win = getCurrentWindow()
  const pos = await win.outerPosition()
  const size = await win.outerSize()
  await win.setSize(new PhysicalSize(size.width + 1, size.height + 1))
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))
  await win.setSize(new PhysicalSize(size.width, size.height))
  await win.setPosition(new PhysicalPosition(pos.x, pos.y))
}

interface UseBubbleOptions {
  timeoutMs?: number
}

export function useBubble(options: UseBubbleOptions = {}) {
  const { timeoutMs = 60000 } = options

  const [bubbleState, setBubbleState] = useState<BubbleState>('hidden')
  const [text, setText] = useState('')
  const [isPinned, setIsPinned] = useState(false)
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const finalizedAtRef = useRef<number | null>(null)

  const clearDismissTimer = useCallback(() => {
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = null
    }
  }, [])

  const startDismissTimer = useCallback(() => {
    clearDismissTimer()
    finalizedAtRef.current = Date.now()
    dismissTimerRef.current = setTimeout(() => {
      setBubbleState('hidden')
      finalizedAtRef.current = null
      nudgeWindowRepaint()
    }, timeoutMs)
  }, [timeoutMs, clearDismissTimer])

  // Called when streaming starts
  const startStreaming = useCallback((initialText: string) => {
    clearDismissTimer()
    setText(initialText)
    setIsPinned(false)
    finalizedAtRef.current = null
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
    setIsPinned(false)
    finalizedAtRef.current = null
    setBubbleState('hidden')
    nudgeWindowRepaint()
  }, [clearDismissTimer])

  const pin = useCallback(() => {
    setIsPinned(true)
    clearDismissTimer()
    finalizedAtRef.current = null
  }, [clearDismissTimer])

  // Dismiss on 'x' key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'x' && bubbleState !== 'hidden') {
        dismiss()
      }
    }
    document.addEventListener('keyup', handler)
    return () => document.removeEventListener('keyup', handler)
  }, [bubbleState, dismiss])

  useEffect(() => {
    return () => clearDismissTimer()
  }, [clearDismissTimer])

  const isVisible = bubbleState !== 'hidden'
  const isStreaming = bubbleState === 'streaming'

  return {
    isVisible,
    text,
    isStreaming,
    isPinned,
    bubbleState,
    timeoutMs,
    finalizedAt: finalizedAtRef.current,
    startStreaming,
    updateText,
    finalize,
    dismiss,
    pin,
  }
}
