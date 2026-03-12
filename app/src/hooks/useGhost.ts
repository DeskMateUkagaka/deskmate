import { useState, useEffect, useCallback } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWindow } from '@tauri-apps/api/window'
import type { GhostPosition } from '../types'

export function useGhost() {
  const [position, setPosition] = useState<GhostPosition>({ x: 100, y: 100 })
  const [isDragging, setIsDragging] = useState(false)
  const [expression, setExpression] = useState<string>('neutral')
  const [expressionImage, setExpressionImage] = useState<string>('')

  useEffect(() => {
    invoke<GhostPosition>('get_ghost_position').then((pos) => {
      setPosition(pos)
      // Window positioning is handled in Ghost.tsx onLoad (after resize)
    })
  }, [])

  useEffect(() => {
    invoke<string>('get_expression_image', { expression }).then((path) => {
      setExpressionImage(path)
    }).catch(() => {
      // Fallback: try neutral
      invoke<string>('get_expression_image', { expression: 'neutral' }).then(setExpressionImage)
    })
  }, [expression])

  const startDrag = useCallback(async () => {
    setIsDragging(true)
    const win = getCurrentWindow()
    await win.startDragging()
    // After drag ends, save position
    const pos = await win.outerPosition()
    const newPos = { x: pos.x, y: pos.y }
    setPosition(newPos)
    invoke('set_ghost_position', { x: newPos.x, y: newPos.y })
    setIsDragging(false)
  }, [])

  const handleMouseMove = useCallback(async (e: React.MouseEvent<HTMLElement>) => {
    const target = e.currentTarget
    const rect = target.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    // Check if mouse is over a transparent pixel
    const canvas = document.createElement('canvas')
    const img = target.querySelector('img')
    if (!img) return

    canvas.width = img.naturalWidth
    canvas.height = img.naturalHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.drawImage(img, 0, 0)
    const scaleX = img.naturalWidth / rect.width
    const scaleY = img.naturalHeight / rect.height
    const pixelData = ctx.getImageData(
      Math.floor(x * scaleX),
      Math.floor(y * scaleY),
      1,
      1
    ).data
    const alpha = pixelData[3]

    const win = getCurrentWindow()
    // If pixel is mostly transparent, let clicks pass through
    await win.setIgnoreCursorEvents(alpha < 30)
  }, [])

  const handleMouseLeave = useCallback(async () => {
    const win = getCurrentWindow()
    await win.setIgnoreCursorEvents(true)
  }, [])

  return {
    position,
    isDragging,
    expression,
    expressionImage,
    setExpression,
    startDrag,
    handleMouseMove,
    handleMouseLeave,
  }
}
