# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

AI-powered desktop companion (Ukagaka) built with Tauri v2. A transparent character sits on the desktop, connected to an OpenClaw AI gateway for chat, expression switching, and skin management.

## Prerequisites

- **Rust** (stable, ≥1.77.2): https://rustup.rs
- **Node.js** (≥18)
- **pnpm**: `npm i -g pnpm`
- **Tauri CLI v2**: `cargo install tauri-cli --version "^2"`
- **Linux system deps** (Debian/Ubuntu):
  ```bash
  sudo apt install libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev
  ```
  Arch: `sudo pacman -S webkit2gtk-4.1 gtk3 libayatana-appindicator librsvg`

## Getting Started

```bash
cd app
pnpm install          # install frontend dependencies
cargo tauri dev       # starts Vite + Tauri with hot reload
```

**NVIDIA GPU workaround**: If you get `Failed to create GBM buffer` errors, run with:
```bash
WEBKIT_DISABLE_COMPOSITING_MODE=1 cargo tauri dev
```

Rust dependencies are fetched automatically by Cargo on first build.

## Build & Dev Commands

All commands run from the `app/` directory:

```bash
# Development (starts Vite + Tauri with hot reload)
cargo tauri dev

# Production build (outputs binary + .deb + .rpm)
cargo tauri build

# TypeScript check only
npx tsc --noEmit

# Rust check only (from app/src-tauri/)
cargo check

# Add frontend dependency
pnpm add <package>

# Add Rust dependency (from app/src-tauri/)
cargo add <crate>
```

## Architecture

### Two-Layer System
- **Rust backend** (`app/src-tauri/src/`): Tauri commands, OpenClaw WebSocket client, skin loader, settings persistence
- **React frontend** (`app/src/`): Components + hooks calling Rust via `invoke()`, Tauri events for streaming data

### OpenClaw Gateway Protocol (Critical)

The gateway is NOT simple request-response. It's a streaming JSON-RPC-over-WebSocket system:

1. Connect → server sends `connect.challenge` with nonce
2. Client sends `connect` RPC with `ConnectParams` (client ID: `gateway-client`, mode: `ui`, protocol: 3, token auth)
3. Server responds with `HelloOk`
4. `chat.send` returns immediate ack `{ runId, status: "started" }` — do NOT use `expectFinal`
5. AI responses stream as separate `chat` EventFrames with `state: delta|final|error|aborted`

Reference implementations in `openclaw/`:
- `scripts/dev/gateway-ws-client.ts` — minimal client
- `src/tui/gateway-chat.ts` — production chat client
- `src/gateway/protocol/schema/logs-chat.ts` — ChatSendParams + ChatEvent schemas

### Expression System

`ChatEventSchema` has NO `expression` field (`additionalProperties: false`). Expressions are parsed client-side from AI text content using `[expression:X]` tags, then stripped from display. Falls back to `neutral`. This is a known fragility — the AI must be prompted to emit these tags.

Valid expressions: `happy`, `sad`, `angry`, `disgusted`, `condescending`, `thinking`, `uwamezukai`, `neutral`

### Action Buttons

Hardcoded client-side ("Tell me more" + "Dismiss"). The gateway protocol has no mechanism for AI-decided buttons — LINE quick replies are channel-specific, not gateway-level.

### Data Flow

```
User types → ChatInputWindow → emit("chat-send") → App listens → sendMessage() → invoke('chat_send') → Rust GatewayClient → OpenClaw WS
OpenClaw WS → Rust EventFrame listener → app.emit("chat-event") → useOpenClaw hook → Bubble
```

### Skin Format

Each skin is a folder under `app/skins/`:
```
skins/<skin-id>/
  manifest.json     # { name, author, version, expressions: { happy: "happy.png", ... } }
  happy.png
  sad.png
  ... (8 PNGs total)
```

### Key State Management

- `GatewayState` (Rust): holds the WebSocket client, managed via `Arc<Mutex<>>`
- `ProactiveState` (Rust): holds the timer stop channel
- `Settings` (Rust): persisted to `$APP_DATA_DIR/settings.json`
- Frontend state: React hooks (`useOpenClaw`, `useBubble`, `useGhost`, `useSkin`, `useSettings`) — no external state library

### WebKitGTK Transparent Window Limitations (Linux)

WebKitGTK has a compositor bug where transparent windows leave ghost artifacts ("bleed") when DOM elements are removed or hidden. The upstream bug ([tauri#12800](https://github.com/tauri-apps/tauri/issues/12800)) was reportedly fixed in WebKitGTK 2.48.0, but bleed still occurs on WebKitGTK 2.50.5 with Sway/Wayland.

**What works and what doesn't:**
- Text content changes during streaming DO trigger repaints (chat bubble text updates fine)
- DOM element removal (`return null`) does NOT trigger repaint — old pixels persist
- CSS property changes (opacity, background, transform) do NOT clear bleed
- `document.body.style.display` toggling does NOT clear bleed
- Opacity transitions cause worse bleed (window becomes fully opaque)
- New elements rendered over the bleed area do NOT paint over it

**Working fix: window size nudge + wait + restore.** Resizing the window by 1px forces the compositor to repaint. Must wait one animation frame (`requestAnimationFrame`) between resize and restore — without the wait, the compositor doesn't process the change. Then restore original size and position. Must use `PhysicalSize`/`PhysicalPosition` (not Logical) to avoid coordinate mismatch on HiDPI Wayland. There is a slight visible budge. See `useBubble.ts` `nudgeWindowRepaint()`.

**Constraint: requires floating window.** On tiling WMs (Sway), `setSize` is ignored for tiled windows. The ghost window must be floating (`for_window [app_id="..."] floating enable` in Sway config).

**Rules:**
- Use separate opaque windows for complex UI panels (settings, skin picker, chat input)
- Lightweight overlays (chat bubble) can live in the transparent window — use the size nudge on dismiss
- Never use opacity transitions on transparent windows
- `setIgnoreCursorEvents` is all-or-nothing for the entire window — no per-element control
- Call `window.setFocus()` after showing a window that needs keyboard input
- Separate windows are opaque (`transparent: false`), hidden by default (`visible: false`), shown/hidden via `win.show()`/`win.hide()`
- Inter-window communication uses Tauri events, not shared React state

### Tauri Capabilities

Permissions are in `app/src-tauri/capabilities/default.json`. If adding new Tauri APIs (e.g., shell, dialog, notification), add the corresponding permission there.

## Remaining Work

See `TODO.md` for the full list. Key items:
- Real character artwork (currently placeholder colored circles)
- Live gateway testing (built against protocol spec, not yet tested against running OpenClaw)
- Hit-testing validation on X11/Wayland
- System prompt configuration for expression tags
- Cross-platform builds (macOS, Windows)
