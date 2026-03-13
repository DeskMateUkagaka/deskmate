import { useCallback, useRef, useEffect, type MouseEvent as ReactMouseEvent } from 'react'
import { convertFileSrc } from '@tauri-apps/api/core'
import { getCurrentWindow, LogicalSize } from '@tauri-apps/api/window'
import { invoke } from '@tauri-apps/api/core'
import { useGhost } from '../hooks/useGhost'
import { restoreWindowPosition, getWindowPosition } from '../lib/moveWindow'

export interface ImageBounds {
  top: number
  bottom: number
  centerX: number
  centerY: number
}

interface GhostProps {
  expressionOverride?: string
  ghostHeightPixels: number
  onLeftClick?: () => void
  onMiddleClick?: () => void
  onRightClick?: (x: number, y: number) => void
  onImageBounds?: (bounds: ImageBounds) => void
}

const DRAG_THRESHOLD = 5 // px before we treat it as a drag

export function Ghost({ expressionOverride, ghostHeightPixels, onLeftClick, onMiddleClick, onRightClick, onImageBounds }: GhostProps) {
  const {
    expressionImage,
  } = useGhost()

  const imageSrc = expressionOverride || (expressionImage ? convertFileSrc(expressionImage) : '')

  const targetHeight = ghostHeightPixels

  const mouseDownPos = useRef<{ x: number; y: number } | null>(null)
  const didDrag = useRef(false)
  const imgRef = useRef<HTMLImageElement>(null)

  // Report image bounds when image loads or window resizes
  useEffect(() => {
    const reportBounds = () => {
      if (imgRef.current && onImageBounds) {
        const rect = imgRef.current.getBoundingClientRect()
        onImageBounds({
          top: rect.top,
          bottom: rect.bottom,
          centerX: rect.left + rect.width / 2,
          centerY: rect.top + rect.height / 2,
        })
      }
    }
    reportBounds()
    window.addEventListener('resize', reportBounds)
    return () => window.removeEventListener('resize', reportBounds)
  }, [onImageBounds, imageSrc])

  console.log('[Ghost] render, imageSrc:', imageSrc ? 'present' : 'empty')

  const handleMouseDown = useCallback((e: ReactMouseEvent<HTMLDivElement>) => {
    console.log('[Ghost] mousedown button:', e.button)
    if (e.button === 0) {
      mouseDownPos.current = { x: e.screenX, y: e.screenY }
      didDrag.current = false
    }
  }, [])

  const handleMouseMove = useCallback((e: ReactMouseEvent<HTMLDivElement>) => {
    // Check if we should start a drag
    if (mouseDownPos.current && !didDrag.current && e.buttons === 1) {
      const dx = e.screenX - mouseDownPos.current.x
      const dy = e.screenY - mouseDownPos.current.y
      if (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD) {
        console.log('[Ghost] drag started')
        didDrag.current = true
        mouseDownPos.current = null
        const win = getCurrentWindow()
        win.startDragging().then(async () => {
          const pos = await getWindowPosition(win)
          invoke('set_ghost_position', { x: pos.x, y: pos.y })
          console.log('[Ghost] drag ended, saved position')
        })
      }
    }
  }, [])

  const handleMouseUp = useCallback((e: ReactMouseEvent<HTMLDivElement>) => {
    console.log('[Ghost] mouseup button:', e.button, 'didDrag:', didDrag.current, 'hasDownPos:', !!mouseDownPos.current)
    if (e.button === 0) {
      mouseDownPos.current = null
      didDrag.current = false
    } else if (e.button === 1) {
      console.log('[Ghost] middle click fired (via mouseup)')
      e.preventDefault()
      onMiddleClick?.()
    }
  }, [onMiddleClick])

  const handleClick = useCallback((e: ReactMouseEvent<HTMLDivElement>) => {
    console.log('[Ghost] click event, button:', e.button, 'didDrag:', didDrag.current)
    if (e.button === 0 && !didDrag.current) {
      console.log('[Ghost] left click fired (via click)')
      onLeftClick?.()
    }
  }, [onLeftClick])

  const handleContextMenu = useCallback((e: ReactMouseEvent<HTMLDivElement>) => {
    console.log('[Ghost] contextmenu fired')
    e.preventDefault()
    onRightClick?.(e.clientX, e.clientY)
  }, [onRightClick])

  const handleAuxClick = useCallback((e: ReactMouseEvent<HTMLDivElement>) => {
    console.log('[Ghost] auxclick button:', e.button)
    if (e.button === 1) {
      e.preventDefault()
    }
  }, [])

  return (
    <div
      className="ghost-container"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onClick={handleClick}
      onMouseLeave={() => {
        mouseDownPos.current = null
      }}
      onContextMenu={handleContextMenu}
      onAuxClick={handleAuxClick}
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'transparent',
      }}
    >
      {imageSrc && (
        <img
          ref={imgRef}
          src={imageSrc}
          alt="ghost"
          draggable={false}
          onLoad={async () => {
            const img = imgRef.current
            if (!img) return
            const win = getCurrentWindow()

            // Resize window, restore saved position, then show
            if (img.naturalWidth > 0 && img.naturalHeight > 0) {
              const aspectRatio = img.naturalWidth / img.naturalHeight
              const targetWidth = Math.round(targetHeight * aspectRatio)
              await win.setSize(new LogicalSize(targetWidth, targetHeight)).catch(() => {})
            }
            await win.show().catch(() => {})
            const pos = await invoke<{ x: number; y: number }>('get_ghost_position')
            await restoreWindowPosition(win, pos.x, pos.y).catch(() => {})

            if (onImageBounds) {
              const rect = img.getBoundingClientRect()
              onImageBounds({
                top: rect.top,
                bottom: rect.bottom,
                centerX: rect.left + rect.width / 2,
                centerY: rect.top + rect.height / 2,
              })
            }
          }}
          style={{
            maxWidth: '100%',
            height: targetHeight,
            maxHeight: targetHeight,
            objectFit: 'contain',
            cursor: 'grab',
            imageRendering: 'auto',
          }}
        />
      )}
    </div>
  )
}
