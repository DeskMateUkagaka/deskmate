import { useState, useRef, useCallback, useEffect, type CSSProperties } from 'react'
import { getCurrentWindow } from '@tauri-apps/api/window'
import { useOcsSkins } from '../hooks/useOcsSkins'
import { debugLog } from '../lib/debugLog'
import type { OcsContentItem } from '../types'

export function GetSkinsWindow() {
  const win = getCurrentWindow()
  const {
    items, loading, totalItems, sortMode,
    installedIds, downloadingId, downloadProgress,
    search, setSort, loadMore, downloadSkin,
  } = useOcsSkins()

  const [searchInput, setSearchInput] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleSearchChange = useCallback((value: string) => {
    setSearchInput(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      debugLog('[GetSkinsWindow] Search:', value)
      search(value)
    }, 300)
  }, [search])

  // Intercept Alt+F4 / window close — hide instead of destroy
  useEffect(() => {
    const unlisten = win.onCloseRequested((e) => {
      e.preventDefault()
      win.hide()
    })
    return () => { unlisten.then(fn => fn()) }
  }, [])

  const handleClose = () => win.hide()

  const panelStyle: CSSProperties = {
    background: '#fff',
    display: 'flex',
    flexDirection: 'column',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
    height: '100vh',
    overflow: 'hidden',
  }

  const headerStyle: CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '14px 20px 10px',
    borderBottom: '1px solid #eee',
    flexShrink: 0,
  }

  const titleStyle: CSSProperties = {
    fontSize: 16,
    fontWeight: 600,
    color: '#1a1a1a',
  }

  const closeButtonStyle: CSSProperties = {
    background: 'transparent',
    border: 'none',
    cursor: 'pointer',
    fontSize: 20,
    color: '#888',
    lineHeight: 1,
    padding: 2,
  }

  const toolbarStyle: CSSProperties = {
    display: 'flex',
    gap: 10,
    padding: '10px 20px',
    flexShrink: 0,
    borderBottom: '1px solid #f0f0f0',
  }

  const searchInputStyle: CSSProperties = {
    flex: 1,
    padding: '7px 12px',
    border: '1px solid #ddd',
    borderRadius: 6,
    fontSize: 13,
    outline: 'none',
  }

  const sortSelectStyle: CSSProperties = {
    padding: '7px 10px',
    border: '1px solid #ddd',
    borderRadius: 6,
    fontSize: 13,
    background: '#fff',
    cursor: 'pointer',
  }

  const scrollAreaStyle: CSSProperties = {
    flex: 1,
    overflowY: 'auto',
    padding: '16px 20px',
  }

  const gridStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
    gap: 14,
  }

  const cardStyle: CSSProperties = {
    background: 'rgba(0,0,0,0.04)',
    borderRadius: 10,
    padding: 12,
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  }

  const thumbnailStyle: CSSProperties = {
    width: '100%',
    height: 100,
    objectFit: 'cover',
    borderRadius: 6,
  }

  const thumbnailPlaceholderStyle: CSSProperties = {
    width: '100%',
    height: 100,
    background: 'rgba(0,0,0,0.06)',
    borderRadius: 6,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 28,
    color: '#bbb',
  }

  const skinNameStyle: CSSProperties = {
    fontSize: 13,
    fontWeight: 600,
    color: '#1a1a1a',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  }

  const metaStyle: CSSProperties = {
    fontSize: 11,
    color: '#888',
    display: 'flex',
    justifyContent: 'space-between',
  }

  const installButtonStyle: CSSProperties = {
    background: '#3060c0',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    padding: '6px 14px',
    fontSize: 12,
    cursor: 'pointer',
    alignSelf: 'flex-start',
  }

  const installedBadgeStyle: CSSProperties = {
    color: '#2a9d2a',
    fontWeight: 600,
    fontSize: 12,
    padding: '6px 0',
  }

  const loadMoreButtonStyle: CSSProperties = {
    display: 'block',
    margin: '20px auto 0',
    padding: '8px 24px',
    background: 'rgba(0,0,0,0.06)',
    border: 'none',
    borderRadius: 6,
    fontSize: 13,
    cursor: 'pointer',
    color: '#333',
  }

  const renderActionArea = (item: OcsContentItem) => {
    if (installedIds.has(item.id)) {
      return <div style={installedBadgeStyle}>Installed</div>
    }
    if (downloadingId === item.id && downloadProgress) {
      const pct = downloadProgress.total
        ? Math.round((downloadProgress.downloaded / downloadProgress.total) * 100)
        : 0
      return (
        <div style={{ width: '100%' }}>
          <div style={{ background: '#e0e0e0', height: 4, borderRadius: 2, overflow: 'hidden' }}>
            <div style={{ background: '#3060c0', height: '100%', width: `${pct}%`, transition: 'width 0.1s' }} />
          </div>
          <div style={{ fontSize: 10, color: '#888', marginTop: 3 }}>{pct}%</div>
        </div>
      )
    }
    return (
      <button
        style={installButtonStyle}
        disabled={downloadingId !== null}
        onClick={() => downloadSkin(item)}
      >
        Install
      </button>
    )
  }

  const renderThumbnail = (item: OcsContentItem) => {
    const src = item.smallpreviewpic1 || item.previewpic1
    if (!src) return <div style={thumbnailPlaceholderStyle}>🎭</div>
    return (
      <ThumbnailImage src={src} style={thumbnailStyle} />
    )
  }

  return (
    <div style={panelStyle}>
      <div style={headerStyle}>
        <span style={titleStyle}>Get Skins</span>
        <button style={closeButtonStyle} onClick={handleClose}>×</button>
      </div>
      <div style={toolbarStyle}>
        <input
          style={searchInputStyle}
          type="text"
          placeholder="Search skins..."
          value={searchInput}
          onChange={e => handleSearchChange(e.target.value)}
        />
        <select
          style={sortSelectStyle}
          value={sortMode}
          onChange={e => setSort(e.target.value)}
        >
          <option value="new">Newest</option>
          <option value="down">Most Downloaded</option>
          <option value="high">Highest Rated</option>
        </select>
      </div>
      <div style={scrollAreaStyle}>
        {loading && items.length === 0 && (
          <div style={{ textAlign: 'center', color: '#888', fontSize: 13, padding: 40 }}>
            Loading...
          </div>
        )}
        {!loading && items.length === 0 && (
          <div style={{ textAlign: 'center', color: '#888', fontSize: 13, padding: 40 }}>
            No skins found
          </div>
        )}
        {items.length > 0 && (
          <div style={gridStyle}>
            {items.map(item => (
              <div key={item.id} style={cardStyle}>
                {renderThumbnail(item)}
                <div style={skinNameStyle}>{item.name}</div>
                <div style={metaStyle}>
                  <span>by {item.personid}</span>
                  <span>{item.downloads} ↓</span>
                </div>
                {renderActionArea(item)}
              </div>
            ))}
          </div>
        )}
        {items.length < totalItems && (
          <button style={loadMoreButtonStyle} onClick={loadMore} disabled={loading}>
            {loading ? 'Loading...' : 'Load More'}
          </button>
        )}
      </div>
    </div>
  )
}

function ThumbnailImage({ src, style }: { src: string, style: CSSProperties }) {
  const [errored, setErrored] = useState(false)
  if (errored) {
    return (
      <div style={{ ...style, background: 'rgba(0,0,0,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, color: '#bbb' }}>
        🎭
      </div>
    )
  }
  return (
    <img
      src={src}
      style={style}
      onError={() => setErrored(true)}
      alt=""
    />
  )
}
