import { useCallback, useRef, type MouseEvent as ReactMouseEvent } from 'react'
import { convertFileSrc } from '@tauri-apps/api/core'
import { getCurrentWindow } from '@tauri-apps/api/window'
import { invoke } from '@tauri-apps/api/core'
import { useGhost } from '../hooks/useGhost'

interface GhostProps {
  expressionOverride?: string
  onLeftClick?: () => void
  onMiddleClick?: () => void
  onRightClick?: (x: number, y: number) => void
}

const DRAG_THRESHOLD = 5 // px before we treat it as a drag

export function Ghost({ expressionOverride, onLeftClick, onMiddleClick, onRightClick }: GhostProps) {
  const {
    expressionImage,
  } = useGhost()

  const mouseDownPos = useRef<{ x: number; y: number } | null>(null)
  const didDrag = useRef(false)

  const imageSrc = expressionOverride || (expressionImage ? convertFileSrc(expressionImage) : '')

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
          const pos = await win.outerPosition()
          invoke('set_ghost_position', { x: pos.x, y: pos.y })
          console.log('[Ghost] drag ended, saved position')
        })
      }
    }
  }, [])

  const handleMouseUp = useCallback((e: ReactMouseEvent<HTMLDivElement>) => {
    console.log('[Ghost] mouseup button:', e.button, 'didDrag:', didDrag.current, 'hasDownPos:', !!mouseDownPos.current)
    if (e.button === 0) {
      if (!didDrag.current && mouseDownPos.current) {
        console.log('[Ghost] left click fired (via mouseup)')
        onLeftClick?.()
      }
      mouseDownPos.current = null
      didDrag.current = false
    } else if (e.button === 1) {
      console.log('[Ghost] middle click fired (via mouseup)')
      e.preventDefault()
      onMiddleClick?.()
    }
  }, [onLeftClick, onMiddleClick])

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
          src={imageSrc}
          alt="ghost"
          draggable={false}
          style={{
            maxWidth: '100%',
            maxHeight: '100%',
            objectFit: 'contain',
            cursor: 'grab',
            imageRendering: 'auto',
          }}
        />
      )}
    </div>
  )
}
