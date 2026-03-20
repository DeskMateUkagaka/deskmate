import { useState, useEffect, useLayoutEffect, useRef, useMemo, type CSSProperties, type ReactNode } from 'react'
import { listen, emit } from '@tauri-apps/api/event'
import { getCurrentWindow, PhysicalSize, PhysicalPosition } from '@tauri-apps/api/window'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github.css'
import type { BubbleTheme, PlacementOrigin } from '../types'
import { debugLog } from '../lib/debugLog'
import type { BubbleItem } from '../hooks/useBubble'

interface BubbleData {
  items: BubbleItem[]
  isVisible: boolean
  timeoutMs: number
  bubbleTheme: BubbleTheme | null
  contentOffsetX: number
  contentOffsetY: number
  origin: PlacementOrigin
}

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
  const val = theme?.[key]
  return typeof val === 'string' ? val : fallback
}

function extractText(node: ReactNode): string {
  if (typeof node === 'string') return node
  if (typeof node === 'number') return String(node)
  if (!node) return ''
  if (Array.isArray(node)) return node.map(extractText).join('')
  if (typeof node === 'object' && 'props' in node) return extractText((node as { props: { children?: ReactNode } }).props.children)
  return ''
}

function CodeCopyButton({ onClick }: { onClick: () => void }) {
  const [copied, setCopied] = useState(false)

  const handle = () => {
    onClick()
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <button
      onClick={handle}
      style={{
        position: 'absolute',
        top: 4,
        right: 4,
        padding: '2px 6px',
        fontSize: '10px',
        borderRadius: 4,
        border: '1px solid rgba(0,0,0,0.15)',
        background: 'var(--code-bg)',
        color: 'var(--code-text)',
        cursor: 'pointer',
        opacity: copied ? 1 : 0.6,
      }}
    >
      {copied ? 'Copied!' : 'Copy'}
    </button>
  )
}

async function nudgeWindowRepaint() {
  const win = getCurrentWindow()
  const pos = await win.outerPosition()
  const size = await win.outerSize()
  await win.setSize(new PhysicalSize(size.width + 1, size.height + 1))
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))
  await win.setSize(new PhysicalSize(size.width, size.height))
  await win.setPosition(new PhysicalPosition(pos.x, pos.y))
  // Wait for compositor to process the restore before caller measures content
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))
}

function BubbleCard({
  item,
  theme,
  timeoutMs,
  accentColor,
  copied,
  setCopied,
}: {
  item: BubbleItem
  theme: BubbleTheme | null
  timeoutMs: number
  accentColor: string
  copied: false | string
  setCopied: (value: false | string) => void
}) {
  const [progress, setProgress] = useState(1)

  useEffect(() => {
    if (!item.finalizedAt || item.isPinned || item.isStreaming) {
      setProgress(1)
      return
    }

    const interval = setInterval(() => {
      const elapsed = Date.now() - item.finalizedAt!
      const remaining = Math.max(0, 1 - elapsed / timeoutMs)
      setProgress(remaining)
      if (remaining <= 0) clearInterval(interval)
    }, 50)

    return () => clearInterval(interval)
  }, [item.finalizedAt, item.id, item.isPinned, item.isStreaming, timeoutMs])

  const bg = themeVal(theme, 'background_color', DEFAULTS.backgroundColor)
  const borderColor = themeVal(theme, 'border_color', DEFAULTS.borderColor)
  const borderWidth = themeVal(theme, 'border_width', DEFAULTS.borderWidth)
  const borderRadius = themeVal(theme, 'border_radius', DEFAULTS.borderRadius)
  const textColor = themeVal(theme, 'text_color', DEFAULTS.textColor)
  const codeBg = themeVal(theme, 'code_background', DEFAULTS.codeBackground)
  const codeText = themeVal(theme, 'code_text_color', DEFAULTS.codeTextColor)
  const fontSize = themeVal(theme, 'font_size', DEFAULTS.fontSize)
  const fontFamily = theme?.font_family ?? undefined
  const copyText = () => {
    navigator.clipboard.writeText(item.text)
    setCopied(item.id)
    setTimeout(() => setCopied(false), 1500)
  }

  const markdownContent = useMemo(() => (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkBreaks]}
      rehypePlugins={[rehypeHighlight]}
      components={{
        pre: ({ children, ...props }) => {
          const copyCode = () => {
            const text = extractText(children)
            navigator.clipboard.writeText(text)
          }

          return (
            <pre {...props} style={{ overflowX: 'auto', background: 'var(--code-bg)', color: 'var(--code-text)', padding: '8px 12px', borderRadius: 6, margin: '8px 0', fontSize: '12px', lineHeight: 1.4, position: 'relative' }}>
              {children}
              <CodeCopyButton onClick={copyCode} />
            </pre>
          )
        },
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
      {item.text}
    </ReactMarkdown>
  ), [item.text, accentColor])

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
    overflowY: 'auto',
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

  const showProgressBar = !item.isStreaming && !item.isPinned && item.finalizedAt !== null

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <div className="bubble-markdown" style={bubbleStyle}>
        <div style={{ minHeight: 20 }}>
          {item.isStreaming ? (
            <span style={{ whiteSpace: 'pre-wrap' }}>
              {item.text}
              <span style={{ display: 'inline-block', marginLeft: 2, animation: 'blink 1s step-end infinite' }}>▋</span>
            </span>
          ) : (
            markdownContent
          )}
        </div>
        {!item.isStreaming && (
          <div style={actionsStyle}>
            <button style={primaryPillStyle} onClick={copyText}>
              {copied === item.id ? 'Copied!' : copied === `selection:${item.id}` ? 'Selection Copied!' : 'Copy (Ctrl+C)'}
            </button>
            {!item.isPinned && (
              <button style={primaryPillStyle} onClick={() => emit('bubble-action', { action: 'pin', id: item.id })}>
                Pin (p)
              </button>
            )}
            <button style={secondaryPillStyle} onClick={() => emit('bubble-action', { action: 'dismiss', id: item.id })}>
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
  )
}

export function BubbleWindow() {
  const [data, setData] = useState<BubbleData>({
    items: [],
    isVisible: false,
    timeoutMs: 60000,
    bubbleTheme: null,
    contentOffsetX: 0,
    contentOffsetY: 0,
    origin: 'center',
  })
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [clampedOffset, setClampedOffset] = useState({ x: 0, y: 0 })
  const [copied, setCopied] = useState<false | string>(false)
  const dataRef = useRef(data)
  dataRef.current = data
  const win = getCurrentWindow()

  useEffect(() => {
    let unlisten: (() => void) | undefined

    listen<BubbleData>('bubble-update', (event) => {
      setData(event.payload)
    }).then((fn) => { unlisten = fn })

    return () => unlisten?.()
  }, [win])

  const prevVisibleRef = useRef(false)
  useEffect(() => {
    const wasVisible = prevVisibleRef.current
    prevVisibleRef.current = data.isVisible

    if (data.isVisible && !wasVisible) {
      debugLog(`[BubbleWindow] becoming visible, items=${data.items.length}`)
      win.show().catch(() => {})
      requestAnimationFrame(() => nudgeWindowRepaint().catch(() => {}))
    } else if (!data.isVisible && wasVisible) {
      nudgeWindowRepaint()
        .then(() => win.hide())
        .catch(() => win.hide())
    }
  }, [data.isVisible, win])

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
  }, [data.contentOffsetX, data.contentOffsetY, data.origin, data.items])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const current = dataRef.current
      const oldest = current.items[0]
      const latest = current.items[current.items.length - 1]
      if (!current.isVisible || !oldest || !latest) return

      if (e.key === 'x' || e.key === 'Escape') {
        emit('bubble-action', { action: 'dismiss', id: oldest.id })
        return
      }

      if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault()
        emit('bubble-pass-through-key', { key: 'Enter' })
        return
      }

      if (e.key === 'c' && (e.ctrlKey || e.metaKey)) {
        const selection = window.getSelection()?.toString()
        if (selection) {
          setCopied(`selection:${latest.id}`)
        } else {
          e.preventDefault()
          navigator.clipboard.writeText(latest.text)
          setCopied(latest.id)
        }

        setTimeout(() => setCopied(false), 1500)
        return
      }

      if (e.key === 'p' && !latest.isPinned && !latest.isStreaming) {
        emit('bubble-action', { action: 'pin', id: latest.id })
      }
    }

    const buttonEnterHandler = (e: Event) => {
      const keyEvent = e as KeyboardEvent
      if (keyEvent.key !== 'Enter' || keyEvent.shiftKey || keyEvent.ctrlKey || keyEvent.metaKey || keyEvent.altKey) return
      keyEvent.preventDefault()
      keyEvent.stopPropagation()
      emit('bubble-pass-through-key', { key: 'Enter' })
    }

    window.addEventListener('keydown', handler, true)
    document.addEventListener('keydown', handler, true)
    document.addEventListener('keypress', buttonEnterHandler, true)
    return () => {
      window.removeEventListener('keydown', handler, true)
      document.removeEventListener('keydown', handler, true)
      document.removeEventListener('keypress', buttonEnterHandler, true)
    }
  }, [])

  const itemSignature = useMemo(() => data.items.map((item) => (
    `${item.id}:${item.isStreaming ? 's' : 'f'}:${item.isPinned ? 'p' : 'u'}:${item.finalizedAt ?? 'n'}`
  )).join('|'), [data.items])

  useEffect(() => {
    if (!data.isVisible) return

    requestAnimationFrame(async () => {
      const el = wrapperRef.current
      const hasStreaming = data.items.some((item) => item.isStreaming)

      // Nudge first to clear WebKitGTK bleed, THEN emit content-sized.
      // If content-sized fires before the nudge completes, App.tsx resizes
      // the window while the nudge is still restoring the old size — race.
      if (!hasStreaming || data.items.length !== 1 || !data.items[0]?.isStreaming) {
        await nudgeWindowRepaint().catch(() => {})
      }

      if (el && !hasStreaming) {
        const PADDING = 8
        const w = el.offsetWidth + PADDING * 2
        const h = el.offsetHeight + PADDING * 2
        debugLog(`[BubbleWindow] content-sized: ${w}x${h}, wrapper=${el.offsetWidth}x${el.offsetHeight}, window=${window.innerWidth}x${window.innerHeight}`)
        emit('bubble-content-sized', { width: w, height: h })
      }
    })
  }, [data.isVisible, itemSignature])

  useEffect(() => {
    if (data.isVisible) {
      requestAnimationFrame(() => nudgeWindowRepaint().catch(() => {}))
    }
  }, [data.isVisible])

  if (!data.isVisible) return null

  const t = data.bubbleTheme
  const accentColor = themeVal(t, 'accent_color', DEFAULTS.accentColor)
  const maxBubbleWidth = t?.max_bubble_width ?? 640
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

  const stackStyle: CSSProperties = {
    position: 'relative',
    width: 'fit-content',
    minWidth: 200,
    maxWidth: Math.min(maxBubbleWidth, window.innerWidth - 8),
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    transform: (clampedOffset.x || clampedOffset.y)
      ? `translate(${clampedOffset.x}px, ${clampedOffset.y}px)`
      : undefined,
  }

  return (
    <div style={outerStyle}>
      <div ref={wrapperRef} style={stackStyle}>
        {data.items.map((item) => (
          <BubbleCard
            key={item.id}
            item={item}
            theme={t}
            timeoutMs={data.timeoutMs}
            accentColor={accentColor}
            copied={copied}
            setCopied={setCopied}
          />
        ))}
      </div>
    </div>
  )
}
