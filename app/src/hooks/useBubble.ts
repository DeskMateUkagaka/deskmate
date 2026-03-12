import { useState, useEffect, useRef, useCallback } from 'react'

export type BubbleState = 'hidden' | 'streaming' | 'visible' | 'dismissing'

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
