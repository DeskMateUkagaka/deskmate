import { useState, useEffect, useCallback, useRef } from 'react'
import { invoke } from '@tauri-apps/api/core'
import type { Settings } from '../types'

const DEFAULT_SETTINGS: Settings = {
  gateway_url: 'ws://127.0.0.1:18789',
  gateway_token: '',
  bubble_timeout_ms: 60000,
  proactive_enabled: false,
  proactive_interval_mins: 60,
  ghost_x: 100,
  ghost_y: 100,
  current_skin_id: 'default',
  ghost_height_pixels: 540,
}

export function useSettings() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS)
  const [isLoaded, setIsLoaded] = useState(false)
  const proactiveRunning = useRef(false)

  useEffect(() => {
    invoke<Settings>('get_settings')
      .then((s) => {
        setSettings(s)
        setIsLoaded(true)
      })
      .catch(() => {
        setIsLoaded(true)
      })
  }, [])

  // Manage proactive dialogue timer based on settings
  useEffect(() => {
    if (!isLoaded) return

    if (settings.proactive_enabled && settings.proactive_interval_mins > 0) {
      // Start proactive timer
      invoke('start_proactive', {
        intervalMins: settings.proactive_interval_mins,
        sessionKey: '', // will use default session
      }).then(() => {
        proactiveRunning.current = true
      }).catch(() => {
        // Gateway might not be connected yet — ignore
      })
    } else if (proactiveRunning.current) {
      invoke('stop_proactive').catch(() => {})
      proactiveRunning.current = false
    }
  }, [isLoaded, settings.proactive_enabled, settings.proactive_interval_mins])

  const updateSettings = useCallback(async (partial: Partial<Settings>) => {
    const next = { ...settings, ...partial }
    setSettings(next)
    await invoke('update_settings', { newSettings: next })
  }, [settings])

  const reloadSettings = useCallback(() => {
    invoke<Settings>('get_settings').then(setSettings).catch(() => {})
  }, [])

  return { settings, updateSettings, reloadSettings, isLoaded }
}
