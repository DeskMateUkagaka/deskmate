import { useState, useEffect, useCallback, useRef } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { listen, emit } from '@tauri-apps/api/event'
import { debugLog } from '../lib/debugLog'
import type { OcsContentItem, OcsBrowseResult, SkinDownloadProgress } from '../types'

export function useOcsSkins() {
  const [items, setItems] = useState<OcsContentItem[]>([])
  const [loading, setLoading] = useState(false)
  const [totalItems, setTotalItems] = useState(0)
  const [searchQuery, setSearchQuery] = useState('')
  const [sortMode, setSortModeState] = useState('new')
  const [page, setPage] = useState(0)
  const [installedIds, setInstalledIds] = useState<Set<string>>(new Set())
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [downloadProgress, setDownloadProgress] = useState<SkinDownloadProgress | null>(null)
  const pageRef = useRef(0)

  const fetchSkins = useCallback(async (params: { search: string, sortmode: string, page: number }, append: boolean) => {
    setLoading(true)
    debugLog('[useOcsSkins] Fetching skins:', params)
    const result = await invoke<OcsBrowseResult>('ocs_browse', {
      params: {
        categories: '464',
        tags: 'deskmate,deskmate-v1',
        search: params.search,
        sortmode: params.sortmode,
        page: params.page,
        pagesize: 20,
      }
    })
    debugLog('[useOcsSkins] Got', result.data.length, 'items, total:', result.totalitems)
    setItems(prev => append ? [...prev, ...result.data] : result.data)
    setTotalItems(result.totalitems)
    setLoading(false)
  }, [])

  // Initial load
  useEffect(() => {
    fetchSkins({ search: '', sortmode: 'new', page: 0 }, false)
    invoke<string[]>('get_installed_skin_ids').then(ids => {
      setInstalledIds(new Set(ids))
    })
  }, [fetchSkins])

  const search = useCallback((query: string) => {
    setSearchQuery(query)
    setPage(0)
    pageRef.current = 0
    fetchSkins({ search: query, sortmode: sortMode, page: 0 }, false)
  }, [fetchSkins, sortMode])

  const setSort = useCallback((mode: string) => {
    setSortModeState(mode)
    setPage(0)
    pageRef.current = 0
    fetchSkins({ search: searchQuery, sortmode: mode, page: 0 }, false)
  }, [fetchSkins, searchQuery])

  const loadMore = useCallback(() => {
    const nextPage = pageRef.current + 1
    pageRef.current = nextPage
    setPage(nextPage)
    fetchSkins({ search: searchQuery, sortmode: sortMode, page: nextPage }, true)
  }, [fetchSkins, searchQuery, sortMode])

  const downloadSkin = useCallback(async (item: OcsContentItem) => {
    setDownloadingId(item.id)
    setDownloadProgress({ downloaded: 0, total: item.downloadsize1 || null })
    debugLog('[useOcsSkins] Downloading skin:', item.name, item.id)

    const unlisten = await listen<SkinDownloadProgress>('skin-download-progress', (event) => {
      setDownloadProgress(event.payload)
    })

    const skinId = await invoke<string>('ocs_download_skin', {
      contentId: item.id,
      downloadUrl: item.downloadlink1,
      filename: item.downloadname1 || `${item.id}.zip`,
    })

    unlisten()
    debugLog('[useOcsSkins] Installed skin:', skinId)
    setInstalledIds(prev => new Set([...prev, item.id]))
    setDownloadingId(null)
    setDownloadProgress(null)
    await emit('skin-installed', { id: skinId })
  }, [])

  return {
    items, loading, totalItems, searchQuery, sortMode,
    installedIds, downloadingId, downloadProgress,
    search, setSort, loadMore, downloadSkin,
  }
}
