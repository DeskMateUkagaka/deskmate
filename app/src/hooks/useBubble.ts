import { useState, useEffect, useRef, useCallback } from 'react'

export interface BubbleItem {
  id: string
  text: string
  isStreaming: boolean
  isPinned: boolean
  finalizedAt: number | null
}

interface UseBubbleOptions {
  timeoutMs?: number
  onDismiss?: () => void
}

export function useBubble(options: UseBubbleOptions = {}) {
  const { timeoutMs = 60000, onDismiss } = options
  const onDismissRef = useRef(onDismiss)
  onDismissRef.current = onDismiss

  const [items, setItems] = useState<BubbleItem[]>([])
  const nextIdRef = useRef(1)
  const activeBubbleIdRef = useRef<string | null>(null)
  const dismissTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  const clearDismissTimer = useCallback((id: string) => {
    const timer = dismissTimersRef.current.get(id)
    if (!timer) return
    clearTimeout(timer)
    dismissTimersRef.current.delete(id)
  }, [])

  const notifyIfEmpty = useCallback((nextItems: BubbleItem[]) => {
    if (nextItems.length === 0) onDismissRef.current?.()
  }, [])

  const dismissById = useCallback((id: string) => {
    clearDismissTimer(id)
    if (activeBubbleIdRef.current === id) activeBubbleIdRef.current = null
    setItems((prev) => {
      const next = prev.filter((item) => item.id !== id)
      notifyIfEmpty(next)
      return next
    })
  }, [clearDismissTimer, notifyIfEmpty])

  const startDismissTimer = useCallback((id: string) => {
    clearDismissTimer(id)
    const timer = setTimeout(() => {
      dismissById(id)
    }, timeoutMs)
    dismissTimersRef.current.set(id, timer)
  }, [timeoutMs, clearDismissTimer, dismissById])

  const startStreaming = useCallback((initialText: string) => {
    const id = String(nextIdRef.current++)
    activeBubbleIdRef.current = id
    setItems((prev) => [...prev, {
      id,
      text: initialText,
      isStreaming: true,
      isPinned: false,
      finalizedAt: null,
    }])
  }, [])

  const updateText = useCallback((newText: string) => {
    const activeId = activeBubbleIdRef.current
    if (!activeId) return
    setItems((prev) => prev.map((item) => (
      item.id === activeId ? { ...item, text: newText } : item
    )))
  }, [])

  const finalize = useCallback(() => {
    const activeId = activeBubbleIdRef.current
    if (!activeId) return
    const finalizedAt = Date.now()
    setItems((prev) => prev.map((item) => (
      item.id === activeId
        ? { ...item, isStreaming: false, finalizedAt }
        : item
    )))
    startDismissTimer(activeId)
    activeBubbleIdRef.current = null
  }, [startDismissTimer])

  const dismiss = useCallback((id?: string) => {
    const targetId = id ?? items[items.length - 1]?.id
    if (!targetId) return
    dismissById(targetId)
  }, [dismissById, items])

  const pin = useCallback((id?: string) => {
    const targetId = id ?? items[items.length - 1]?.id
    if (!targetId) return
    clearDismissTimer(targetId)
    setItems((prev) => prev.map((item) => (
      item.id === targetId
        ? { ...item, isPinned: true, finalizedAt: null }
        : item
    )))
  }, [clearDismissTimer, items])

  useEffect(() => {
    return () => {
      for (const timer of dismissTimersRef.current.values()) {
        clearTimeout(timer)
      }
      dismissTimersRef.current.clear()
    }
  }, [])

  const isVisible = items.length > 0
  const currentItem = items[items.length - 1] ?? null
  const isStreaming = currentItem?.isStreaming ?? false

  return {
    items,
    currentItem,
    isVisible,
    isStreaming,
    timeoutMs,
    startStreaming,
    updateText,
    finalize,
    dismiss,
    dismissById,
    pin,
  }
}
