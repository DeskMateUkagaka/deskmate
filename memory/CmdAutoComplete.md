# Slash Command Autocomplete

## Overview

When the DeskMate client connects to the OpenClaw gateway, it silently sends `/commands` to retrieve the list of available slash commands. These are parsed from the plain-text response and shown as an autocomplete dropdown when the user types `/` anywhere in the chat input.

## How It Works

### Data Flow

```
Gateway connect → "connected" status → silent "/commands" chat.send → chat events (delta → final)
  → _silent_fetch_run_id intercepts → parse_commands_response() → SlashCommand[]
  → _input.set_commands(commands) → ChatInputWindow stores list
  → User types "/" → filter commands → show dropdown
  → User selects → insert at cursor → dropdown dismissed → Enter sends as normal chat
```

### Silent Fetch Mechanism

After the gateway reports "connected" status, `DeskMate._fetch_slash_commands()` checks the local cache first (24h TTL). If stale or missing, it sends `/commands` as a regular `chat.send` RPC. The response is intercepted in `_on_chat_event()` by matching `_silent_fetch_run_id` — events matching this ID are silently swallowed and never reach the chat bubble.

**Critical detail:** `_silent_fetch_run_id` is the **sole defense** against the `/commands` response leaking into the bubble. The check is at the top of `_on_chat_event()` and returns early before any bubble updates.

Guards:
- Cache check prevents re-sending on every reconnect within 24h
- Handles `error`/`aborted` states (cleans up run ID, graceful degradation)

### File Cache (24h TTL)

Parsed commands are cached to `~/.config/deskmate/slash_commands.json` with a timestamp. On connect, `_fetch_slash_commands()` checks the cache first:
1. If cache exists and age < 24h and commands non-empty → use cached, skip gateway fetch
2. Otherwise → send `/commands`, parse response, save to cache

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

`parse_commands_response()` in `app/src/lib/commands.py` uses regex to extract `{ name, description }` pairs from lines matching `/name ... - Description`.

### Autocomplete UI

The dropdown is an `_AutocompletePopup` QWidget child of `ChatInputWindow`, positioned above the text input. It shows up to 8 filtered items with command name (bold) and description. Dark themed to match the input card.

Trigger detection (`_find_slash_trigger()`):
- Searches backwards from cursor for `/`
- Stops at whitespace (the `/` must be preceded by whitespace or be at position 0)
- Rejects if partial text contains spaces

Keyboard navigation:
- `ArrowDown`/`ArrowUp`: navigate items (wraps around)
- `Enter`/`Tab`: insert selected command at cursor position
- `Escape`: dismiss dropdown
- When dropdown is NOT visible, keys behave normally (Enter sends message)

## Files

| File | Role |
|------|------|
| `app/src/lib/commands.py` | `SlashCommand` dataclass, `parse_commands_response()`, cache load/save |
| `app/src/windows/chat_input.py` | `_AutocompletePopup`, `_find_slash_trigger()`, keyboard handling |
| `app/main.py` | Silent fetch trigger, `_silent_fetch_run_id` interception, cache management |

## Limitations

- **No argument autocomplete** — only command names, not their arguments
- **No category grouping** — dropdown is a flat filtered list
- **Delay on first launch** — commands aren't available until the gateway connects and responds. Subsequent launches use the file cache (instant).
- **Parser is fragile** — depends on the `/name  - Description` text format from OpenClaw's `buildCommandsMessage()`. If the format changes, the parser breaks silently (returns empty list, graceful degradation).
- **Aliases not indexed** — `/think` is autocompleted but its aliases `/thinking` and `/t` are not (they're in parentheses and discarded by the parser).

## OpenClaw Backend Reference

Commands are defined in the OpenClaw repo at:
- `src/auto-reply/commands-registry.data.ts` — 50+ commands via `defineChatCommand()`
- `src/auto-reply/commands-registry.ts` — `listChatCommands()`, `listNativeCommandSpecs()`
- `src/auto-reply/skill-commands.ts` — dynamically discovered skill commands
- `src/auto-reply/status.ts` — `buildCommandsMessage()` generates the text response

The gateway protocol has NO `commands.list` RPC. This feature works by sending `/commands` as a regular chat message and parsing the text response — no backend modifications required.
