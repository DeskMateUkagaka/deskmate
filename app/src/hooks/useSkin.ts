import { useState, useEffect, useCallback } from 'react'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import type { SkinInfo } from '../types'
import { debugLog } from '../lib/debugLog'

interface UseSkinReturn {
  currentSkin: SkinInfo | null
  skins: SkinInfo[]
  switchSkin: (id: string) => Promise<void>
  getEmotionUrl: (emotion: string) => string
  reloadSkins: () => void
}

export function useSkin(): UseSkinReturn {
  const [currentSkin, setCurrentSkin] = useState<SkinInfo | null>(null)
  const [skins, setSkins] = useState<SkinInfo[]>([])
  const [emotionUrls, setEmotionUrls] = useState<Record<string, string>>({})

  useEffect(() => {
    invoke<SkinInfo[]>('list_skins').then(setSkins).catch(() => {})
    invoke<SkinInfo>('get_current_skin').then(setCurrentSkin).catch(() => {})
  }, [])

  // Preload emotion images whenever skin changes — uses skin's own emotion list
  useEffect(() => {
    if (!currentSkin) return

    const urls: Record<string, string> = {}
    const promises = currentSkin.emotions.map(async (emotion) => {
      try {
        const path = await invoke<string>('get_emotion_image', { emotion })
        urls[emotion] = convertFileSrc(path)
      } catch {
        // ignore missing emotions
      }
    })

    Promise.all(promises).then(() => setEmotionUrls({ ...urls }))
  }, [currentSkin])

  const switchSkin = useCallback(async (id: string) => {
    await invoke('switch_skin', { skinId: id })
    const skin = await invoke<SkinInfo>('get_current_skin')
    setCurrentSkin(skin)
  }, [])

  const getEmotionUrl = useCallback((emotion: string): string => {
    debugLog(`[useSkin] getEmotionUrl('${emotion}') available=[${Object.keys(emotionUrls).join(',')}]`)
    if (emotionUrls[emotion]) return emotionUrls[emotion]
    if (emotion !== 'neutral') {
      debugLog(`[useSkin] Emotion '${emotion}' not found in skin, falling back to neutral`)
    }
    return emotionUrls['neutral'] ?? ''
  }, [emotionUrls])

  const reloadSkins = useCallback(async () => {
    await invoke('reload_skins')
    invoke<SkinInfo[]>('list_skins').then(setSkins).catch(() => {})
    invoke<SkinInfo>('get_current_skin').then(setCurrentSkin).catch(() => {})
  }, [])

  // Auto-reload when a new skin is installed from Get Skins
  useEffect(() => {
    const unlisten = listen('skin-installed', () => { reloadSkins() })
    return () => { unlisten.then(fn => fn()) }
  }, [reloadSkins])

  return { currentSkin, skins, switchSkin, getEmotionUrl, reloadSkins }
}
