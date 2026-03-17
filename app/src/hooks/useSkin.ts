import { useState, useEffect, useCallback } from 'react'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import type { SkinInfo, Expression, } from '../types'
import { ALL_EXPRESSIONS } from '../types'

interface UseSkinReturn {
  currentSkin: SkinInfo | null
  skins: SkinInfo[]
  switchSkin: (id: string) => Promise<void>
  getExpressionUrl: (expression: Expression) => string
  reloadSkins: () => void
}

export function useSkin(): UseSkinReturn {
  const [currentSkin, setCurrentSkin] = useState<SkinInfo | null>(null)
  const [skins, setSkins] = useState<SkinInfo[]>([])
  const [expressionUrls, setExpressionUrls] = useState<Partial<Record<Expression, string>>>({})

  useEffect(() => {
    invoke<SkinInfo[]>('list_skins').then(setSkins).catch(() => {})
    invoke<SkinInfo>('get_current_skin').then(setCurrentSkin).catch(() => {})
  }, [])

  // Preload expression images whenever skin changes
  useEffect(() => {
    if (!currentSkin) return

    const urls: Partial<Record<Expression, string>> = {}
    const promises = ALL_EXPRESSIONS.map(async (expr) => {
      try {
        const path = await invoke<string>('get_expression_image', { expression: expr })
        urls[expr] = convertFileSrc(path)
      } catch {
        // ignore missing expressions
      }
    })

    Promise.all(promises).then(() => setExpressionUrls({ ...urls }))
  }, [currentSkin])

  const switchSkin = useCallback(async (id: string) => {
    await invoke('switch_skin', { skinId: id })
    const skin = await invoke<SkinInfo>('get_current_skin')
    setCurrentSkin(skin)
  }, [])

  const getExpressionUrl = useCallback((expression: Expression): string => {
    return expressionUrls[expression] ?? expressionUrls['neutral'] ?? ''
  }, [expressionUrls])

  const reloadSkins = useCallback(async () => {
    await invoke('reload_skins')
    invoke<SkinInfo[]>('list_skins').then(setSkins).catch(() => {})
    invoke<SkinInfo>('get_current_skin').then(setCurrentSkin).catch(() => {})
  }, [])

  return { currentSkin, skins, switchSkin, getExpressionUrl, reloadSkins }
}
