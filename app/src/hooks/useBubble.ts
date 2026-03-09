import { useState, useEffect, useRef, useCallback } from 'react'

export type BubbleState = 'hidden' | 'streaming' | 'visible' | 'dismissing'

const PREVIEW_LENGTH = 100

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
      setBubbleState('dismissing')
      // After animation, fully hide
      setTimeout(() => setBubbleState('hidden'), 300)
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
    setBubbleState('dismissing')
    setTimeout(() => setBubbleState('hidden'), 300)
  }, [clearDismissTimer])

  const expand = useCallback(() => {
    setIsExpanded(true)
    // Reset dismiss timer when user interacts
    startDismissTimer()
  }, [startDismissTimer])

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
  const displayText = isExpanded ? text : text.slice(0, PREVIEW_LENGTH)
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
