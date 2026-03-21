# Slash Command Autocomplete

## Overview

When the DeskMate client connects to the OpenClaw gateway, it silently sends `/commands` to retrieve the list of available slash commands. These are parsed from the plain-text response and shown as an autocomplete dropdown when the user types `/` anywhere in the chat input.

## How It Works

### Data Flow

```
Gateway connect → HelloOk → silent "/commands" chat.send → chat events (delta → final)
  → silentFetchRunIdRef intercepts → parseCommandsResponse() → SlashCommand[]
  → App.tsx emits "slash-commands" Tauri event → ChatInputWindow stores in state
  → User types "/" → filter commands → show dropdown
  → User selects → insert at cursor → dropdown dismissed → Enter sends as normal chat
```

### Silent Fetch Mechanism

After the gateway connection is established (detected via polling `connectionStatus`), `useOpenClaw` automatically sends `/commands` as a regular `chat.send` RPC. The response is intercepted in the `chat-event` listener using a `silentFetchRunIdRef` — events matching this runId are silently swallowed and never reach the chat bubble.

**Critical detail:** `silentFetchRunIdRef` is the **sole defense** against the `/commands` response leaking into the bubble. The existing `runIdRef` filter does NOT protect here — when `runIdRef.current` is `''` (initial state, before the user sends any message), the `&&` short-circuits and all events pass through.

Guards:
- `commandsFetchedRef` prevents re-sending `/commands` on every 5-second poll cycle
- Resets on disconnect so commands are re-fetched on reconnect
- Handles `error`/`aborted` states (cleans up ref, graceful degradation)

### Parsing

The `/commands` response is plain text grouped by category:

```
ℹ️ Slash commands

Session
  /new  - Start a new session.
  /reset  - Reset the current session.

Options
  /think <level> (/thinking, /t) - Set thinking level.
```

`parseCommandsResponse()` in `app/src/lib/parseCommands.ts` uses regex to extract `{ name, description }` pairs from lines matching `/name ... - Description`.

### Autocomplete UI

The dropdown renders inside `ChatInputWindow` (same Tauri window) in document flow below the input panel — NOT absolutely positioned, because WebKitGTK hard-clips content at the window boundary. `resizeToFit()` includes the dropdown's `offsetHeight` so the window grows to contain it.

Trigger detection (`findSlashTrigger`):
- Searches backwards from cursor for `/`
- Stops at whitespace (the `/` must be preceded by whitespace or be at position 0)
- Rejects if partial text contains spaces
- Works anywhere in the text, not just at position 0

Keyboard navigation:
- `ArrowDown`/`ArrowUp`: navigate items (wraps around)
- `Enter`/`Tab`: insert selected command at cursor position
- `Escape`: dismiss dropdown
- When dropdown is NOT visible, keys behave normally (Enter sends message)

### Inter-Window Communication

ChatInputWindow is a separate Tauri window — it can't share React state with App.tsx. Commands are passed via the `"slash-commands"` Tauri event:
- Emitted when `slashCommands` state changes in `useOpenClaw`
- Re-emitted in `showChatInput()` because the window may not have been mounted for the initial event (Tauri events are fire-and-forget)

## Files

| File | Role |
|------|------|
| `app/src/types/index.ts` | `SlashCommand` interface |
| `app/src/lib/parseCommands.ts` | Parser for `/commands` plain-text response |
| `app/src/hooks/useOpenClaw.ts` | Silent fetch, event interception, `slashCommands` state |
| `app/src/App.tsx` | Emits `"slash-commands"` event to ChatInputWindow |
| `app/src/windows/ChatInputWindow.tsx` | Autocomplete dropdown UI, keyboard navigation, command insertion |

## Limitations

- **No argument autocomplete** — only command names, not their arguments
- **No category grouping** — dropdown is a flat filtered list
- **5-second delay** — commands aren't available until the first polling cycle detects `connected` status. Could be eliminated by adding a Rust-side `"gateway-connected"` event that fires immediately after HelloOk.
- **Parser is fragile** — depends on the `/name  - Description` text format from OpenClaw's `buildCommandsMessage()`. If the format changes, the parser breaks silently (returns empty list, graceful degradation).
- **Aliases not indexed** — `/think` is autocompleted but its aliases `/thinking` and `/t` are not (they're in parentheses and discarded by the parser).

## OpenClaw Backend Reference

Commands are defined in the OpenClaw repo at:
- `src/auto-reply/commands-registry.data.ts` — 50+ commands via `defineChatCommand()`
- `src/auto-reply/commands-registry.ts` — `listChatCommands()`, `listNativeCommandSpecs()`
- `src/auto-reply/skill-commands.ts` — dynamically discovered skill commands
- `src/auto-reply/status.ts` — `buildCommandsMessage()` generates the text response

The gateway protocol has NO `commands.list` RPC. This feature works by sending `/commands` as a regular chat message and parsing the text response — no backend modifications required.
