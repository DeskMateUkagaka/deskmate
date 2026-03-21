import { useState, useEffect, useRef, useCallback } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import { debugLog } from '../lib/debugLog'
import { parseCommandsResponse } from '../lib/parseCommands'
import type { SlashCommand } from '../types'

export type ChatState = 'idle' | 'sending' | 'streaming' | 'error'
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

// Matches the Rust ChatEvent struct emitted via app.emit("chat-event")
// Field names match Rust's #[serde(rename = "...")] camelCase output
interface ChatEvent {
  runId: string
  sessionKey: string
  seq: number
  state: 'delta' | 'final' | 'error' | 'aborted'
  message?: {
    role: string
    content: Array<{ type: string; text?: string }>
  }
  errorMessage?: string
  stopReason?: string
}


function parseEmotion(text: string): string {
  const match = text.match(/\[emotion:(\w+)\]/)
  if (!match) return 'neutral'
  return match[1]
}

function stripEmotionTags(text: string): string {
  return text.replace(/\[emotion:\w+\]/g, '').trim()
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
  const [currentEmotion, setCurrentEmotion] = useState('neutral')
  const [slashCommands, setSlashCommands] = useState<SlashCommand[]>([])

  const accumulatedRef = useRef('')
const sessionKeyRef = useRef<string>('main')
  const runIdRef = useRef<string>('')
  const unlistenRef = useRef<UnlistenFn | null>(null)
  const silentFetchRunIdRef = useRef<string | null>(null)
  const commandsFetchedRef = useRef<boolean>(false)
  const hasEverConnectedRef = useRef(false)

  // Connect on mount
  useEffect(() => {
    let cancelled = false

    async function connect() {
      setConnectionStatus('connecting')
      try {
        const settings = await invoke<{ gateway_url: string; gateway_token: string }>('get_settings')
        debugLog('[useOpenClaw] connecting to gateway:', settings.gateway_url)
        await invoke('connect_gateway', {
          url: settings.gateway_url,
          token: settings.gateway_token || null,
        })
        // Don't set 'connected' here — connect_gateway returns immediately.
        // The polling interval below will pick up the actual status.
        if (!cancelled) setConnectionStatus('connecting')
      } catch (e) {
        console.error('[useOpenClaw] connect failed:', e)
        if (!cancelled) setConnectionStatus('error')
      }
    }

    connect()

    // Listen for reactive connection status events from Rust
    let statusUnlisten: UnlistenFn | null = null
    listen<string>('connection-status-changed', (event) => {
      if (!cancelled) {
        const status = event.payload as ConnectionStatus
        setConnectionStatus(status)
        if (status === 'connected') hasEverConnectedRef.current = true
      }
    }).then((fn) => { statusUnlisten = fn })

    // Poll connection status as fallback safety net
    const interval = setInterval(async () => {
      if (cancelled) return
      try {
        const status = await invoke<string>('get_connection_status')
        if (!cancelled) {
          setConnectionStatus(status as ConnectionStatus)
          if (status === 'connected') hasEverConnectedRef.current = true
        }
      } catch {
        // ignore
      }
    }, 2000)

    return () => {
      cancelled = true
      clearInterval(interval)
      statusUnlisten?.()
    }
  }, [])

  // Subscribe to chat events
  useEffect(() => {
    let cancelled = false

    async function subscribe() {
      const unlisten = await listen<ChatEvent>('chat-event', (event) => {
        if (cancelled) return
        const evt = event.payload

        // Silent /commands fetch interception — this is the PRIMARY defense
        // against the response leaking into the chat bubble. runIdRef does NOT
        // protect when it's '' (initial state), so this check is load-bearing.
        if (evt.runId && evt.runId === silentFetchRunIdRef.current) {
          if (evt.state === 'final') {
            const text = extractTextFromMessage(evt.message)
            const commands = parseCommandsResponse(text)
            debugLog(`[useOpenClaw] parsed ${commands.length} slash commands from /commands response`)
            setSlashCommands(commands)
            silentFetchRunIdRef.current = null
          } else if (evt.state === 'error' || evt.state === 'aborted') {
            silentFetchRunIdRef.current = null
          }
          // Silently swallow all events (delta, final, error, aborted) for this runId
          return
        }

        // Only process events for our current run
        if (runIdRef.current && evt.runId !== runIdRef.current) return

        if (evt.state === 'delta') {
          // Gateway sends full accumulated text in each delta (not incremental chunks)
          const deltaText = extractTextFromMessage(evt.message)
          debugLog(`[chat-event] delta seq=${evt.seq} len=${deltaText.length} text="${deltaText}"`)
          accumulatedRef.current = deltaText

          // Reset thinking timer on each delta


          const emotion = parseEmotion(accumulatedRef.current)
          const display = stripEmotionTags(accumulatedRef.current)
          debugLog(`[chat-event] delta parsed emotion='${emotion}' display="${display.slice(0, 80)}"`)
          setCurrentEmotion(emotion)
          setCurrentResponse(display)
          setChatState('streaming')
        } else if (evt.state === 'final') {
          // Final message — do a final parse of accumulated text
          const finalText = extractTextFromMessage(evt.message)
          debugLog(`[chat-event] final seq=${evt.seq} len=${finalText.length} text="${finalText}"`)
          if (finalText) {
            accumulatedRef.current = finalText
          }

          const emotion = parseEmotion(accumulatedRef.current)
          const display = stripEmotionTags(accumulatedRef.current)
          debugLog(`[chat-event] final parsed emotion='${emotion}' display="${display.slice(0, 80)}"`)
          setCurrentEmotion(emotion)
          setCurrentResponse(display)
          setChatState('idle')
        } else if (evt.state === 'error') {

          setChatState('error')
          setCurrentResponse(evt.errorMessage ?? 'Unknown error')
        } else if (evt.state === 'aborted') {

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

  // Silently fetch /commands to populate slash command autocomplete
  const fetchCommands = useCallback(async () => {
    if (commandsFetchedRef.current) return
    commandsFetchedRef.current = true
    try {
      const runId = await invoke<string>('chat_send', {
        sessionKey: sessionKeyRef.current,
        message: '/commands',
      })
      silentFetchRunIdRef.current = runId
      debugLog('[useOpenClaw] silent /commands fetch started, runId:', runId)
    } catch (e) {
      commandsFetchedRef.current = false
      debugLog('[useOpenClaw] failed to fetch commands: ' + e)
    }
  }, [])

  // Handle mid-stream disconnect: append [connection lost] to partial response
  useEffect(() => {
    if (connectionStatus === 'disconnected') {
      if (chatState === 'streaming' || chatState === 'sending') {
        accumulatedRef.current += '\n\n[connection lost]'
        setCurrentResponse(accumulatedRef.current)
        setCurrentEmotion('neutral')
        setChatState('idle')
      }
    }
  }, [connectionStatus]) // eslint-disable-line react-hooks/exhaustive-deps

  // Trigger fetch on connect, reset guard on disconnect for reconnect support
  useEffect(() => {
    if (connectionStatus === 'connected') {
      fetchCommands()
    } else {
      commandsFetchedRef.current = false
    }
  }, [connectionStatus, fetchCommands])

  const sendMessage = useCallback(async (text: string) => {
    debugLog('[useOpenClaw] sendMessage called:', text, 'sessionKey:', sessionKeyRef.current)

    // Debug shortcut: "ack" returns a hardcoded response without hitting the gateway
    if (text.toLowerCase() === 'ack') {
      accumulatedRef.current = 'ACK'
      setCurrentResponse('ACK')
      setCurrentEmotion('neutral')
      setChatState('streaming')
      setTimeout(() => setChatState('idle'), 500)
      return
    }

    // Debug shortcut: "emo" returns a random non-neutral emotion to test emotion switching
    if (text.toLowerCase() === 'emo') {
      try {
        const skin = await invoke<{ emotions: string[] }>('get_current_skin')
        const nonNeutral = skin.emotions.filter((e: string) => e !== 'neutral')
        const picked = nonNeutral.length > 0
          ? nonNeutral[Math.floor(Math.random() * nonNeutral.length)]
          : 'neutral'
        const response = `emotion test [emotion:${picked}]`
        accumulatedRef.current = response
        setCurrentResponse(stripEmotionTags(response))
        setCurrentEmotion(picked)
        setChatState('streaming')
        setTimeout(() => setChatState('idle'), 500)
      } catch (e) {
        debugLog('[useOpenClaw] emo: failed to get skin emotions:', e)
        accumulatedRef.current = 'emotion test [emotion:neutral]'
        setCurrentResponse('emotion test')
        setCurrentEmotion('neutral')
        setChatState('streaming')
        setTimeout(() => setChatState('idle'), 500)
      }
      return
    }

    // Debug shortcut: "md" returns sample Markdown to test bubble rendering + theming
    // Simulates real streaming by feeding text character-by-character
    if (text.toLowerCase() === 'md') {
      const sample = `# Hello from Markdown!

Here's some **bold**, *italic*, and \`inline code\`.

## A code block

\`\`\`python
def greet(name: str) -> str:
    """Say hello with style."""
    return f"Hello, {name}! 🎉"

for i in range(3):
    print(greet("World"))
\`\`\`

## A list

- First item
- Second item with **emphasis**
- Third item

> This is a blockquote. It should look nice.

| Header 1 | Header 2 |
|----------|----------|
| Cell A   | Cell B   |
| Cell C   | Cell D   |

And a [link](https://example.com) for good measure.`
      accumulatedRef.current = ''
      setCurrentResponse('')
      setCurrentEmotion('thinking')
      setChatState('streaming')
      // Stream ~10 chars at a time, ~30ms apart (simulates real gateway deltas)
      const chunkSize = 10
      let pos = 0
      const streamInterval = setInterval(() => {
        pos = Math.min(pos + chunkSize, sample.length)
        const partial = sample.slice(0, pos)
        accumulatedRef.current = partial
        setCurrentResponse(partial)
        if (pos >= sample.length) {
          clearInterval(streamInterval)
          setCurrentEmotion('neutral')
          setChatState('idle')
        }
      }, 30)
      return
    }

    // Check connection status before sending
    try {
      const status = await invoke<string>('get_connection_status')
      debugLog('[useOpenClaw] connection status:', status)
      if (status !== 'connected') {
        setChatState('error')
        setCurrentResponse(`Gateway not connected (status: ${status}). Check Settings.`)
        return
      }
    } catch (e) {
      console.error('[useOpenClaw] status check failed:', e)
    }

    accumulatedRef.current = ''
    setCurrentResponse('')
    setCurrentEmotion('thinking')
    setChatState('sending')

    try {
      const runId = await invoke<string>('chat_send', {
        sessionKey: sessionKeyRef.current,
        message: text,
      })
      debugLog('[useOpenClaw] chat_send returned runId:', runId)
      runIdRef.current = runId
    } catch (e) {
      console.error('[useOpenClaw] chat_send failed:', e)
      setChatState('error')
      setCurrentResponse('Failed to send message')
    }
  }, [])

  const abortChat = useCallback(async () => {
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

  const resetEmotion = useCallback(() => {
    setCurrentEmotion('neutral')
  }, [])

  const isStreaming = chatState === 'streaming' || chatState === 'sending'
  const isReconnecting = hasEverConnectedRef.current && (connectionStatus === 'disconnected' || connectionStatus === 'connecting')

  return {
    sendMessage,
    abortChat,
    resetEmotion,
    connectionStatus,
    currentResponse,
    currentEmotion,
    isStreaming,
    isReconnecting,
    chatState,
    slashCommands,
  }
}
