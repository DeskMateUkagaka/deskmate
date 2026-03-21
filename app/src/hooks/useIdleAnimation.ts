import { useState, useEffect, useRef, useCallback } from 'react'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import type { SkinInfo } from '../types'
import { debugLog } from '../lib/debugLog'

interface UseIdleAnimationOptions {
  skin: SkinInfo | null
  enabled: boolean
}

interface UseIdleAnimationReturn {
  /** APNG asset URL to display, or null when not animating */
  idleOverrideUrl: string | null
  /** Increments each play — use as React key on <img> to force APNG replay */
  idlePlayCount: number
  /** Call on any user interaction to reset the idle countdown */
  resetIdleTimer: () => void
}

export function useIdleAnimation({ skin, enabled }: UseIdleAnimationOptions): UseIdleAnimationReturn {
  const [idleOverrideUrl, setIdleOverrideUrl] = useState<string | null>(null)
  const [idlePlayCount, setIdlePlayCount] = useState(0)

  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const animTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const enabledRef = useRef(enabled)
  enabledRef.current = enabled
  const skinRef = useRef(skin)
  skinRef.current = skin

  const hasAnimations = !!skin && skin.idle_animations.length > 0

  const clearTimers = useCallback(() => {
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current)
      idleTimerRef.current = null
    }
    if (animTimerRef.current) {
      clearTimeout(animTimerRef.current)
      animTimerRef.current = null
    }
  }, [])

  // Stable ref for the start function so async callbacks always get the latest version
  const startIdleTimerRef = useRef<() => void>(() => {})

  const startIdleTimer = useCallback(() => {
    const s = skinRef.current
    if (!s || s.idle_animations.length === 0) return
    clearTimers()

    const baseMs = s.idle_interval_seconds * 1000
    const jitter = baseMs * (Math.random() * 0.2 - 0.1) // ±10%
    const delayMs = baseMs + jitter

    debugLog(`[useIdleAnimation] starting idle timer: ${Math.round(delayMs)}ms (base=${baseMs}, jitter=${Math.round(jitter)})`)

    const skinIdAtSchedule = s.id

    idleTimerRef.current = setTimeout(async () => {
      idleTimerRef.current = null

      // Verify skin hasn't changed and we're still enabled
      const currentSkin = skinRef.current
      if (!enabledRef.current || !currentSkin || currentSkin.id !== skinIdAtSchedule) return

      // Pick a random animation
      const idx = Math.floor(Math.random() * currentSkin.idle_animations.length)
      const anim = currentSkin.idle_animations[idx]
      debugLog(`[useIdleAnimation] timer fired, playing: ${anim.file} (duration=${anim.duration_ms}ms)`)

      // Resolve file path via Tauri command
      let path: string
      try {
        path = await invoke<string>('get_idle_animation_path', { filename: anim.file })
      } catch (e) {
        debugLog(`[useIdleAnimation] failed to get path for '${anim.file}':`, e)
        // Skip this animation, restart timer
        if (enabledRef.current && skinRef.current?.id === skinIdAtSchedule) {
          startIdleTimerRef.current()
        }
        return
      }

      // Re-check after async — skin or enabled may have changed
      if (!enabledRef.current || skinRef.current?.id !== skinIdAtSchedule) return

      const url = convertFileSrc(path)
      setIdleOverrideUrl(url)
      setIdlePlayCount(c => c + 1)

      // Schedule restoration after duration
      animTimerRef.current = setTimeout(() => {
        animTimerRef.current = null
        debugLog('[useIdleAnimation] animation complete, restoring expression')
        setIdleOverrideUrl(null)
        // Restart idle timer for next cycle
        if (enabledRef.current) {
          startIdleTimerRef.current()
        }
      }, anim.duration_ms)
    }, delayMs)
  }, [clearTimers])

  startIdleTimerRef.current = startIdleTimer

  const resetIdleTimer = useCallback(() => {
    // Cancel any active animation
    if (animTimerRef.current) {
      clearTimeout(animTimerRef.current)
      animTimerRef.current = null
      setIdleOverrideUrl(null)
      debugLog('[useIdleAnimation] interaction interrupted animation')
    }
    // Cancel pending idle timer
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current)
      idleTimerRef.current = null
    }
    // Restart if enabled and skin has animations
    if (enabledRef.current && skinRef.current && skinRef.current.idle_animations.length > 0) {
      startIdleTimerRef.current()
    }
  }, [])

  // Start/stop based on enabled state and skin
  useEffect(() => {
    if (enabled && hasAnimations) {
      setIdlePlayCount(0)
      startIdleTimer()
    } else {
      clearTimers()
      setIdleOverrideUrl(null)
    }
    return clearTimers
  }, [enabled, skin?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  return { idleOverrideUrl, idlePlayCount, resetIdleTimer }
}
