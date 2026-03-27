# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

AI-powered desktop companion (DeskMate) built with PySide6 (Qt6). A transparent character sits on the desktop, connected to an OpenClaw AI gateway for chat, expression switching, and skin management. Target audience is geek/otaku users who want a beautiful AI frontend — visual perfection is non-negotiable.

The app was migrated from Tauri v2 (Rust + React) to PySide6 (Python). The old codebase is preserved in `app-tauri/` for reference. The migration was driven by WebKitGTK's unfixable transparent window bleed bug.

## Getting Started

```bash
cd app
pip install -r requirements.txt   # or: uv pip install -r requirements.txt
python3 main.py
```

**Dependencies:** PySide6 (Qt6 + QtWebEngine), PyYAML, websockets, cryptography

**First run** creates `~/.config/deskmate/` with default settings and a generated Ed25519 device identity.

**Sway users** need this in their config:
```
for_window [app_id="deskmate"] floating enable
```

## Architecture

### Orchestrator Pattern

`app/main.py` (`DeskMate` class) is the central orchestrator. It owns all windows, the gateway client, settings, skins, and idle animation manager. All inter-window coordination happens here via Qt signals.

### Five Independent Windows

All windows are separate transparent frameless QWidgets — never overlays in a single window (overlays swallow clicks in transparent areas).

- **GhostWindow** (`src/windows/ghost.py`): Character sprite rendered via **QWebEngineView** (Chromium `<img>` tag) for browser-quality Lanczos scaling. Drag uses `windowHandle().startSystemMove()` for native Wayland support. Mouse events are intercepted via recursive `eventFilter` on QWebEngineView's internal child widgets.

- **BubbleWindow** (`src/windows/bubble.py`): Chat content via **QWebEngineView** with embedded HTML/CSS/JS. Handles markdown rendering, streaming cursor animation, per-item dismiss/pin timers, action buttons, code block copy. JS↔Python communication via QWebChannel (`_BubbleBridge`).

- **ChatInputWindow** (`src/windows/chat_input.py`): Native Qt text editor with slash command autocomplete popup. Enter sends, Shift+Enter newlines, Escape dismisses. Auto-grows up to 6 lines.

- **SettingsWindow** (`src/windows/settings.py`): Form for gateway URL/token, appearance, behavior settings.

- **SkinPickerWindow** (`src/windows/skin_picker.py`): Grid of skin cards with preview images.

### OpenClaw Gateway Protocol

Streaming JSON-RPC-over-WebSocket. The connection flow is critical:

1. Connect → server sends `connect.challenge` with nonce
2. Client signs nonce with Ed25519 device identity (v3 pipe-separated payload format), sends `connect` RPC. **Without device identity, the server strips all scopes and `chat.send` fails.**
3. Server responds with `HelloOk`
4. `chat.send` returns immediate ack `{ runId, status: "started" }`
5. AI responses stream as separate `chat` EventFrames with `state: delta|final|error|aborted`

Gateway client (`src/gateway/client.py`) runs in asyncio, integrated with Qt via QTimer polling at 16ms. Callbacks marshal to Qt main thread via `QTimer.singleShot(0, ...)`.

### Expression System

Expressions are parsed **client-side** from AI text using `[emotion:X]` tags (regex in `src/lib/parse.py`), then stripped before display. The gateway protocol has no expression field. The AI must be prompted to emit these tags. Falls back to `neutral`.

### Action Buttons

Parsed from `[btn:message]` tags in AI text. When clicked, the button text is re-sent as a new chat message.

### Data Flow

```
User types → ChatInputWindow.message_sent signal → DeskMate._on_chat_send()
  → asyncio: ChatSession.send() → GatewayClient.request("chat.send") → WebSocket
  → EventFrames stream back → on_event callback → QTimer.singleShot(0, ...) → _on_chat_event()
  → parse_emotion() → ghost.set_expression() | strip_all_tags() → bubble.update_text()
  → state=="final" → bubble.finalize() + parse_buttons() → bubble.set_buttons()
```

### Silent `/commands` Fetch

After gateway connects, DeskMate silently sends `/commands` to fetch available slash commands. The response is intercepted by matching `_silent_fetch_run_id` — it never appears in the chat bubble. Parsed commands are cached to `~/.config/deskmate/slash_commands.json` (24h TTL) and passed to ChatInputWindow for autocomplete.

### Asyncio ↔ Qt Integration

```python
self._loop = asyncio.new_event_loop()
self._async_timer = QTimer()
self._async_timer.setInterval(16)  # ~60fps pump
self._async_timer.timeout.connect(self._pump_asyncio)
```

Gateway callbacks arrive in the asyncio context and must be marshalled to the Qt main thread via `QTimer.singleShot(0, lambda: ...)`.

### Settings

Persisted to `~/.config/deskmate/config.yaml` (YAML with comment preservation). `SettingsManager` in `src/lib/settings.py`. Key fields: `gateway_url`, `gateway_token`, `current_skin_id`, `ghost_height_pixels`, `bubble_timeout_ms`, `idle_interval_seconds`, `quake_terminal.*`.

Transient state (window positions) is stored separately in `~/.config/deskmate/state.yaml` via `AppStateManager` — this keeps frequently-changing values like `ghost_x`/`ghost_y` out of the user-edited config file.

### Skin Format

```
app/skins/<skin-id>/
  manifest.yaml     # name, author, emotions: {happy: [happy.png, ...], ...}
  neutral.png       # Required emotion
  preview.png       # For skin picker
  idle_animation.apng  # Optional
```

Manifest can also define `bubble_placement`, `input_placement` (UiPlacement with origin), `bubble` theme, and `idle_animations` with duration_ms.

### Idle Animation System

`IdleAnimationManager` (`src/lib/idle.py`) uses QTimer with jitter (interval ±10%). Picks random animation from skin manifest, emits `idle_override` signal to ghost, waits `duration_ms`, then emits `idle_cleared`. Resets on any user interaction.

### Quake Terminal

`QuakeTerminalManager` (`src/lib/quake_terminal.py`) spawns an external terminal process (auto-detects foot/kitty/alacritty/etc). Toggle via tray menu or SIGUSR1 signal (`pkill -USR1 -x python3`). Show/hide via `swaymsg` (Sway) or `xdotool` (X11).

## Platform-Specific Notes

### Wayland (Sway)

- `QWidget.move()` is ignored — the compositor controls window position. Ghost drag uses `startSystemMove()` which delegates to the compositor natively.
- Popup positioning works via Qt's built-in positioning (no `swaymsg` needed for popups since Qt handles initial placement).
- `app_id` is set to `deskmate` via `setDesktopFileName("deskmate")`.
- Quake terminal uses `swaymsg '[title="deskmate-quake"] ...'` for show/hide/position.

### Fractional Scaling

Sway with fractional scale (e.g., 1.333x) causes blurry rendering in ALL Qt/GTK apps — Sway sends integer scale 2 to apps, then downscales. This is a compositor limitation, not fixable from the app side. Integer scales (1x, 2x) render sharply.

## Debugging

- All logging goes to stdout via Python `logging` module
- Debug command: type `emo` in chat input to switch to a random expression
- `SIGUSR1` toggles quake terminal: `pkill -USR1 -x python3`

## Feature Documentation

Detailed design docs in `memory/`:
- `BTN.md` — Dynamic `[btn:msg]` button tags
- `CmdAutoComplete.md` — Slash command autocomplete
- `IDLE.md` — Idle animation system
- `QUAKE.md` — Quake-style dropdown terminal
- `SKINS.md` — Skin format and skin picker
- `BLEED.md` — WebKitGTK bleed bug documentation (historical, no longer affects PySide6 version)

## Legacy Tauri App

The original Tauri v2 codebase is preserved in `app-tauri/` for reference. It contains the Rust backend, React frontend, and extensive documentation of WebKitGTK transparency workarounds that are no longer needed in the PySide6 version.

## VCS

- Always use `jj` (jujutsu) and never use `git` directly.
- After `jj desc` always run `jj new` to prevent changes mixing into the previous revision.
- When requested, use `jj workspace` to create a separate workspace to work in parallel (git equivalent of git worktree).
