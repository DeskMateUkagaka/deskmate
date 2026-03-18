import { useState, useEffect, useLayoutEffect, useRef, type CSSProperties } from 'react'
import { listen, emit } from '@tauri-apps/api/event'
import { getCurrentWindow, PhysicalSize, PhysicalPosition } from '@tauri-apps/api/window'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github.css'
import type { BubbleTheme, PlacementOrigin } from '../types'

interface BubbleData {
  text: string
  isStreaming: boolean
  isVisible: boolean
  isPinned: boolean
  timeoutMs: number
  finalizedAt: number | null
  bubbleTheme: BubbleTheme | null
  contentOffsetX: number
  contentOffsetY: number
  origin: PlacementOrigin
}

// Defaults matching the original hardcoded styles
const DEFAULTS = {
  backgroundColor: '#fff',
  borderColor: '#d0d0d0',
  borderWidth: '1px',
  borderRadius: '12px',
  textColor: '#1a1a1a',
  accentColor: '#3060c0',
  codeBackground: '#f5f5f5',
  codeTextColor: '#333333',
  fontSize: '13px',
}

function themeVal(theme: BubbleTheme | null, key: keyof BubbleTheme, fallback: string): string {
  return theme?.[key] ?? fallback
}

async function nudgeWindowRepaint() {
  const win = getCurrentWindow()
  const pos = await win.outerPosition()
  const size = await win.outerSize()
  await win.setSize(new PhysicalSize(size.width + 1, size.height + 1))
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))
  await win.setSize(new PhysicalSize(size.width, size.height))
  await win.setPosition(new PhysicalPosition(pos.x, pos.y))
}

export function BubbleWindow() {
  const [data, setData] = useState<BubbleData>({
    text: '',
    isStreaming: false,
    isVisible: false,
    isPinned: false,
    timeoutMs: 60000,
    finalizedAt: null,
    bubbleTheme: null,
    contentOffsetX: 0,
    contentOffsetY: 0,
    origin: 'center',
  })
  const [progress, setProgress] = useState(1)
  const wasStreamingRef = useRef(false)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [clampedOffset, setClampedOffset] = useState({ x: 0, y: 0 })
  const [copied, setCopied] = useState<false | 'full' | 'selection'>(false)
  const copiedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const copyText = () => {
    navigator.clipboard.writeText(data.text)
    setCopied('full')
    if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current)
    copiedTimerRef.current = setTimeout(() => setCopied(false), 1500)
  }
  const win = getCurrentWindow()

  // Listen for bubble state updates from main window
  useEffect(() => {
    let unlisten: (() => void) | undefined
    listen<BubbleData>('bubble-update', (event) => {
      setData(event.payload)
    }).then((fn) => { unlisten = fn })
    return () => unlisten?.()
  }, [win])

  // Show/hide window — nudge before hide to clear bleed from DOM removal
  const prevVisibleRef = useRef(false)
  useEffect(() => {
    const wasVisible = prevVisibleRef.current
    prevVisibleRef.current = data.isVisible

    if (data.isVisible && !wasVisible) {
      // Became visible — show window, nudge once to clear previous bleed
      win.show().catch(() => {})
      requestAnimationFrame(() => nudgeWindowRepaint().catch(() => {}))
    } else if (!data.isVisible && wasVisible) {
      // Became hidden — nudge to clear bleed, then hide
      nudgeWindowRepaint()
        .then(() => win.hide())
        .catch(() => win.hide())
    }
  }, [data.isVisible, win])

  // Progress bar countdown
  useEffect(() => {
    if (!data.finalizedAt || data.isPinned) {
      setProgress(1)
      return
    }
    const interval = setInterval(() => {
      const elapsed = Date.now() - data.finalizedAt!
      const remaining = Math.max(0, 1 - elapsed / data.timeoutMs)
      setProgress(remaining)
      if (remaining <= 0) clearInterval(interval)
    }, 50)
    return () => clearInterval(interval)
  }, [data.finalizedAt, data.timeoutMs, data.isPinned])

  // Clamp content offset so the visible bubble stays within the window.
  // Available shift space depends on origin alignment (which corner content is anchored to).
  useLayoutEffect(() => {
    if (!wrapperRef.current) {
      setClampedOffset({ x: 0, y: 0 })
      return
    }
    const padding = 4
    const wrapperW = wrapperRef.current.offsetWidth
    const wrapperH = wrapperRef.current.offsetHeight
    const spaceX = Math.max(0, window.innerWidth - 2 * padding - wrapperW)
    const spaceY = Math.max(0, window.innerHeight - 2 * padding - wrapperH)

    // Origin determines where content sits naturally, which affects how far it can shift
    const o = data.origin
    const isLeft = o === 'top-left' || o === 'bottom-left'
    const isRight = o === 'top-right' || o === 'bottom-right'
    const isTop = o === 'top-left' || o === 'top-right'
    const isBottom = o === 'bottom-left' || o === 'bottom-right'

    const minX = isRight ? -spaceX : isLeft ? 0 : -spaceX / 2
    const maxX = isRight ? 0 : isLeft ? spaceX : spaceX / 2
    const minY = isBottom ? -spaceY : isTop ? 0 : -spaceY / 2
    const maxY = isBottom ? 0 : isTop ? spaceY : spaceY / 2

    setClampedOffset({
      x: Math.max(minX, Math.min(data.contentOffsetX, maxX)),
      y: Math.max(minY, Math.min(data.contentOffsetY, maxY)),
    })
  }, [data.contentOffsetX, data.contentOffsetY, data.origin, data.text, data.isStreaming])

  // Nudge repaint when pin state changes (buttons/progress bar appear/disappear)
  const prevPinnedRef = useRef(data.isPinned)
  useEffect(() => {
    if (data.isPinned !== prevPinnedRef.current && data.isVisible) {
      prevPinnedRef.current = data.isPinned
      requestAnimationFrame(() => nudgeWindowRepaint().catch(() => {}))
    }
  }, [data.isPinned, data.isVisible])

  // Dismiss on 'x' key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!data.isVisible) return
      if (e.key === 'x' || e.key === 'Escape') {
        emit('bubble-action', { action: 'dismiss' })
      } else if (e.key === 'c' && (e.ctrlKey || e.metaKey)) {
        const selection = window.getSelection()?.toString()
        if (!selection) {
          e.preventDefault()
          copyText()
        } else {
          // Let browser handle the copy, then show feedback
          setCopied('selection')
          if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current)
          copiedTimerRef.current = setTimeout(() => setCopied(false), 1500)
        }
      } else if (e.key === 'p' && !data.isPinned) {
        emit('bubble-action', { action: 'pin' })
      }
    }
    document.addEventListener('keyup', handler)
    return () => document.removeEventListener('keyup', handler)
  }, [data.isVisible])

  // Nudge repaint on finalization (streaming → rendered Markdown) to clear bleed
  useEffect(() => {
    if (data.isStreaming) {
      wasStreamingRef.current = true
    } else if (wasStreamingRef.current && data.isVisible) {
      wasStreamingRef.current = false
      requestAnimationFrame(() => nudgeWindowRepaint().catch(() => {}))
    }
  }, [data.isStreaming, data.isVisible])

  // Nudge repaint when bubble becomes visible (clears bleed from previous dismiss)
  useEffect(() => {
    if (data.isVisible) {
      requestAnimationFrame(() => nudgeWindowRepaint().catch(() => {}))
    }
  }, [data.isVisible])

  if (!data.isVisible) return null

  const t = data.bubbleTheme
  const bg = themeVal(t, 'background_color', DEFAULTS.backgroundColor)
  const borderColor = themeVal(t, 'border_color', DEFAULTS.borderColor)
  const borderWidth = themeVal(t, 'border_width', DEFAULTS.borderWidth)
  const borderRadius = themeVal(t, 'border_radius', DEFAULTS.borderRadius)
  const textColor = themeVal(t, 'text_color', DEFAULTS.textColor)
  const accentColor = themeVal(t, 'accent_color', DEFAULTS.accentColor)
  const codeBg = themeVal(t, 'code_background', DEFAULTS.codeBackground)
  const codeText = themeVal(t, 'code_text_color', DEFAULTS.codeTextColor)
  const fontSize = themeVal(t, 'font_size', DEFAULTS.fontSize)
  const fontFamily = t?.font_family ?? undefined
  const maxBubbleWidth = t?.max_bubble_width ?? 640
  const maxBubbleHeight = t?.max_bubble_height ?? 540

  const alignH = data.origin.includes('left') ? 'flex-start'
    : data.origin.includes('right') ? 'flex-end' : 'center'
  const alignV = data.origin.startsWith('top') ? 'flex-start'
    : data.origin.startsWith('bottom') ? 'flex-end' : 'center'

  const outerStyle: CSSProperties = {
    width: '100vw',
    height: '100vh',
    background: 'transparent',
    display: 'flex',
    alignItems: alignV,
    justifyContent: alignH,
    padding: 4,
  }

  const bubbleWrapperStyle: CSSProperties = {
    position: 'relative',
    width: 'fit-content',
    minWidth: 200,
    maxWidth: Math.min(maxBubbleWidth, window.innerWidth - 8),
    transform: (clampedOffset.x || clampedOffset.y)
      ? `translate(${clampedOffset.x}px, ${clampedOffset.y}px)`
      : undefined,
  }

  const bubbleStyle: CSSProperties = {
    background: bg,
    borderRadius,
    padding: '12px 14px',
    border: `${borderWidth} solid ${borderColor}`,
    fontSize,
    lineHeight: 1.5,
    color: textColor,
    fontFamily,
    wordBreak: 'break-word',
    userSelect: 'text',
    WebkitUserSelect: 'text',
    cursor: 'text',
    maxHeight: maxBubbleHeight,
    overflowY: 'auto',
    // CSS custom properties for highlight.js overrides
    '--code-bg': codeBg,
    '--code-text': codeText,
  } as CSSProperties

  const actionsStyle: CSSProperties = {
    display: 'flex',
    gap: 6,
    marginTop: 10,
    flexWrap: 'wrap',
  }

  const pillStyle: CSSProperties = {
    padding: '4px 10px',
    borderRadius: 20,
    border: 'none',
    cursor: 'pointer',
    fontSize: 11,
    fontWeight: 500,
    transition: 'background 0.15s',
  }

  const primaryPillStyle: CSSProperties = {
    ...pillStyle,
    background: `color-mix(in srgb, ${accentColor} 15%, transparent)`,
    color: accentColor,
  }

  const secondaryPillStyle: CSSProperties = {
    ...pillStyle,
    background: 'rgba(0,0,0,0.07)',
    color: '#555',
  }

  const progressBarContainerStyle: CSSProperties = {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: 3,
    background: 'rgba(0,0,0,0.06)',
  }

  const progressBarStyle: CSSProperties = {
    height: '100%',
    width: `${progress * 100}%`,
    background: `color-mix(in srgb, ${accentColor} 40%, transparent)`,
    borderRadius: `0 0 ${borderRadius} ${borderRadius}`,
    transition: 'width 0.1s linear',
  }

  const showProgressBar = !data.isStreaming && !data.isPinned && data.finalizedAt !== null

  return (
    <div style={outerStyle}>
      <div ref={wrapperRef} style={bubbleWrapperStyle}>
        <div className="bubble-markdown" style={bubbleStyle}>
          <div style={{ minHeight: 20 }}>
            {data.isStreaming ? (
              <span style={{ whiteSpace: 'pre-wrap' }}>
                {data.text}
                <span style={{ display: 'inline-block', marginLeft: 2, animation: 'blink 1s step-end infinite' }}>▋</span>
              </span>
            ) : (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
                components={{
                  pre: ({ children, ...props }) => (
                    <pre {...props} style={{ overflowX: 'auto', background: 'var(--code-bg)', color: 'var(--code-text)', padding: '8px 12px', borderRadius: 6, margin: '8px 0', fontSize: '12px', lineHeight: 1.4 }}>
                      {children}
                    </pre>
                  ),
                  code: ({ children, className, ...props }) => {
                    if (!className) {
                      return (
                        <code {...props} style={{ background: 'var(--code-bg)', color: 'var(--code-text)', padding: '1px 4px', borderRadius: 3, fontSize: '0.9em' }}>
                          {children}
                        </code>
                      )
                    }
                    return <code className={className} {...props}>{children}</code>
                  },
                  a: ({ children, href, ...props }) => (
                    <a {...props} href={href} style={{ color: accentColor, textDecoration: 'underline' }} target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  ),
                }}
              >
                {data.text}
              </ReactMarkdown>
            )}
          </div>
          {!data.isStreaming && (
            <div style={actionsStyle}>
              <button style={primaryPillStyle} onClick={copyText}>
                {copied === 'full' ? 'Copied!' : copied === 'selection' ? 'Selection Copied!' : 'Copy (Ctrl+C)'}
              </button>
              {!data.isPinned && (
                <button style={primaryPillStyle} onClick={() => emit('bubble-action', { action: 'pin' })}>
                  Pin (p)
                </button>
              )}
              <button style={secondaryPillStyle} onClick={() => emit('bubble-action', { action: 'dismiss' })}>
                Dismiss (x)
              </button>
            </div>
          )}
        </div>
        {showProgressBar && (
          <div style={progressBarContainerStyle}>
            <div style={progressBarStyle} />
          </div>
        )}
      </div>
    </div>
  )
}
