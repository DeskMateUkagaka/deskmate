import { useState, useEffect, useRef, useCallback } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import type { Expression } from '../types'

export type ChatState = 'idle' | 'sending' | 'streaming' | 'error'
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

// Matches the Rust ChatEvent struct emitted via app.emit("chat-event")
interface ChatEvent {
  run_id: string
  session_key: string
  seq: number
  state: 'delta' | 'final' | 'error' | 'aborted'
  message?: {
    role: string
    content: Array<{ type: string; text?: string }>
  }
  error_message?: string
  stop_reason?: string
}

interface SessionInfo {
  key: string
  display_name?: string
}

const VALID_EXPRESSIONS: Expression[] = [
  'happy', 'sad', 'angry', 'disgusted', 'condescending', 'thinking', 'uwamezukai', 'neutral'
]

function parseExpression(text: string): Expression {
  const match = text.match(/\[expression:(\w+)\]/)
  if (!match) return 'neutral'
  const expr = match[1] as Expression
  return VALID_EXPRESSIONS.includes(expr) ? expr : 'neutral'
}

function stripExpressionTags(text: string): string {
  return text.replace(/\[expression:\w+\]/g, '').trim()
}

function extractTextFromMessage(message?: ChatEvent['message']): string {
  if (!message?.content) return ''
  return message.content
    .filter((b) => b.type === 'text' && b.text)
    .map((b) => b.text!)
    .join('')
}

export function useOpenClaw() {
  const [chatState, setChatState] = useState<ChatState>('idle')
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected')
  const [currentResponse, setCurrentResponse] = useState('')
  const [currentExpression, setCurrentExpression] = useState<Expression>('neutral')

  const accumulatedRef = useRef('')
  const thinkingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const sessionKeyRef = useRef<string>('')
  const runIdRef = useRef<string>('')
  const unlistenRef = useRef<UnlistenFn | null>(null)

  // Connect on mount
  useEffect(() => {
    let cancelled = false

    async function connect() {
      setConnectionStatus('connecting')
      try {
        const settings = await invoke<{ gateway_url: string; gateway_token: string }>('get_settings')
        await invoke('connect_gateway', {
          url: settings.gateway_url,
          token: settings.gateway_token || null,
        })
        if (!cancelled) setConnectionStatus('connected')

        // Try to get default session
        const sessions = await invoke<SessionInfo[]>('list_sessions')
        if (sessions.length > 0) {
          sessionKeyRef.current = sessions[0].key
        }
      } catch {
        if (!cancelled) setConnectionStatus('error')
      }
    }

    connect()

    // Poll connection status
    const interval = setInterval(async () => {
      if (cancelled) return
      try {
        const status = await invoke<string>('get_connection_status')
        if (!cancelled) setConnectionStatus(status as ConnectionStatus)
      } catch {
        // ignore
      }
    }, 5000)

    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  // Subscribe to chat events
  useEffect(() => {
    let cancelled = false

    async function subscribe() {
      const unlisten = await listen<ChatEvent>('chat-event', (event) => {
        if (cancelled) return
        const evt = event.payload

        // Only process events for our current run
        if (runIdRef.current && evt.run_id !== runIdRef.current) return

        if (evt.state === 'delta') {
          const deltaText = extractTextFromMessage(evt.message)
          accumulatedRef.current += deltaText

          // Reset thinking timer on each delta
          if (thinkingTimerRef.current) {
            clearTimeout(thinkingTimerRef.current)
            thinkingTimerRef.current = null
          }

          const expr = parseExpression(accumulatedRef.current)
          const display = stripExpressionTags(accumulatedRef.current)
          setCurrentExpression(expr)
          setCurrentResponse(display)
          setChatState('streaming')
        } else if (evt.state === 'final') {
          // Final message — do a final parse of accumulated text
          const finalText = extractTextFromMessage(evt.message)
          if (finalText) {
            accumulatedRef.current = finalText
          }

          if (thinkingTimerRef.current) {
            clearTimeout(thinkingTimerRef.current)
            thinkingTimerRef.current = null
          }

          const expr = parseExpression(accumulatedRef.current)
          const display = stripExpressionTags(accumulatedRef.current)
          setCurrentExpression(expr)
          setCurrentResponse(display)
          setChatState('idle')
        } else if (evt.state === 'error') {
          if (thinkingTimerRef.current) {
            clearTimeout(thinkingTimerRef.current)
            thinkingTimerRef.current = null
          }
          setChatState('error')
          setCurrentResponse(evt.error_message ?? 'Unknown error')
        } else if (evt.state === 'aborted') {
          if (thinkingTimerRef.current) {
            clearTimeout(thinkingTimerRef.current)
            thinkingTimerRef.current = null
          }
          setChatState('idle')
        }
      })
      unlistenRef.current = unlisten
    }

    subscribe()

    return () => {
      cancelled = true
      unlistenRef.current?.()
    }
  }, [])

  const sendMessage = useCallback(async (text: string) => {
    accumulatedRef.current = ''
    setCurrentResponse('')
    setCurrentExpression('neutral')
    setChatState('sending')

    // 5s thinking timeout
    if (thinkingTimerRef.current) clearTimeout(thinkingTimerRef.current)
    thinkingTimerRef.current = setTimeout(() => {
      setCurrentExpression('thinking')
    }, 5000)

    try {
      const runId = await invoke<string>('chat_send', {
        sessionKey: sessionKeyRef.current,
        message: text,
      })
      runIdRef.current = runId
    } catch {
      if (thinkingTimerRef.current) {
        clearTimeout(thinkingTimerRef.current)
        thinkingTimerRef.current = null
      }
      setChatState('error')
      setCurrentResponse('Failed to send message')
    }
  }, [])

  const abortChat = useCallback(async () => {
    if (thinkingTimerRef.current) {
      clearTimeout(thinkingTimerRef.current)
      thinkingTimerRef.current = null
    }
    try {
      await invoke('chat_abort', {
        sessionKey: sessionKeyRef.current,
        runId: runIdRef.current,
      })
    } catch {
      // ignore
    }
    setChatState('idle')
  }, [])

  const isStreaming = chatState === 'streaming' || chatState === 'sending'

  return {
    sendMessage,
    abortChat,
    connectionStatus,
    currentResponse,
    currentExpression,
    isStreaming,
    chatState,
  }
}
