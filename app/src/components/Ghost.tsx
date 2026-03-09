import { useState, useCallback, type MouseEvent } from 'react'
import { convertFileSrc } from '@tauri-apps/api/core'
import { useGhost } from '../hooks/useGhost'

interface GhostProps {
  expressionOverride?: string
  onLeftClick?: () => void
  onRightClick?: (x: number, y: number) => void
}

export function Ghost({ expressionOverride, onLeftClick, onRightClick }: GhostProps) {
  const {
    expressionImage,
    startDrag,
    handleMouseMove,
    handleMouseLeave,
  } = useGhost()

  const [isDragging, setIsDragging] = useState(false)

  const imageSrc = expressionOverride || (expressionImage ? convertFileSrc(expressionImage) : '')

  const handleMouseDown = useCallback(async (e: MouseEvent<HTMLImageElement>) => {
    if (e.button === 0) {
      setIsDragging(false)
      await startDrag()
      // startDrag is async and resolves after drag ends
      setIsDragging(false)
    }
  }, [startDrag])

  const handleClick = useCallback((e: MouseEvent<HTMLDivElement>) => {
    if (e.button === 0 && !isDragging) {
      onLeftClick?.()
    }
  }, [isDragging, onLeftClick])

  const handleContextMenu = useCallback((e: MouseEvent<HTMLDivElement>) => {
    e.preventDefault()
    onRightClick?.(e.clientX, e.clientY)
  }, [onRightClick])

  return (
    <div
      className="ghost-container"
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
      onContextMenu={handleContextMenu}
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
          onMouseDown={handleMouseDown}
          style={{
            maxWidth: '100%',
            maxHeight: '100%',
            objectFit: 'contain',
            cursor: 'grab',
            imageRendering: 'auto',
          }}
          crossOrigin="anonymous"
        />
      )}
    </div>
  )
}
