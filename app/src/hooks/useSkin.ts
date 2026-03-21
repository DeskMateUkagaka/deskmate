import { useState, useEffect, useCallback, useRef } from 'react'
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
  const [emotionUrls, setEmotionUrls] = useState<Record<string, string[]>>({})

  useEffect(() => {
    invoke<SkinInfo[]>('list_skins').then(setSkins).catch(() => {})
    invoke<SkinInfo>('get_current_skin').then(setCurrentSkin).catch(() => {})
  }, [])

  // Preload all emotion image variants whenever skin changes
  useEffect(() => {
    if (!currentSkin) return

    const urls: Record<string, string[]> = {}
    const promises = currentSkin.emotions.map(async (emotion) => {
      try {
        const paths = await invoke<string[]>('get_emotion_images', { emotion })
        urls[emotion] = paths.map(p => convertFileSrc(p))
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

  // Cache the last random pick per emotion so re-renders don't flicker.
  // A new random pick happens only when the emotion name changes.
  const lastPickRef = useRef<{ emotion: string; url: string }>({ emotion: '', url: '' })

  const getEmotionUrl = useCallback((emotion: string): string => {
    debugLog(`[useSkin] getEmotionUrl('${emotion}') available=[${Object.keys(emotionUrls).join(',')}]`)
    // Return cached pick if same emotion
    if (lastPickRef.current.emotion === emotion && lastPickRef.current.url) {
      return lastPickRef.current.url
    }
    const pick = (urls: string[]) => urls[Math.floor(Math.random() * urls.length)]
    const urls = emotionUrls[emotion]
    let result: string
    if (urls?.length) {
      result = pick(urls)
    } else {
      if (emotion !== 'neutral') {
        debugLog(`[useSkin] Emotion '${emotion}' not found in skin, falling back to neutral`)
      }
      const neutralUrls = emotionUrls['neutral']
      result = neutralUrls?.length ? pick(neutralUrls) : ''
    }
    lastPickRef.current = { emotion, url: result }
    return result
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
