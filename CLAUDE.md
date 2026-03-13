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
- `visibility: hidden` + `width/height: 0` + `overflow: hidden` (keeping element in DOM) does NOT clear bleed
- Rendering a semi-transparent element over the bleed area does NOT clear bleed
- Rendering transparent text (`color: transparent`) over the bleed area with changing content does NOT clear bleed — only *visible* text triggers repaints
- **Only known working fix remains the window size nudge** (`nudgeWindowRepaint()`)
- `document.body.style.display` toggling does NOT clear bleed
- Opacity transitions cause worse bleed (window becomes fully opaque)
- New elements rendered over the bleed area do NOT paint over it

**Working fix: window size nudge + wait + restore.** Resizing the window by 1px forces the compositor to repaint. Must wait one animation frame (`requestAnimationFrame`) between resize and restore — without the wait, the compositor doesn't process the change. Then restore original size and position. Must use `PhysicalSize`/`PhysicalPosition` (not Logical) to avoid coordinate mismatch on HiDPI Wayland. There is a slight visible budge. See `useBubble.ts` `nudgeWindowRepaint()`.

**Constraint: requires floating window.** On tiling WMs (Sway), `setSize` is ignored for tiled windows. The ghost window must be floating (`for_window [app_id="..."] floating enable` in Sway config).

**The fundamental tradeoff on Wayland (affects almost all modern Linux):**
1. **Separate windows** can't be positioned programmatically — the compositor controls placement. Compositor-specific workarounds (e.g. `swaymsg`) exist but are too slow for responsive UI.
2. **Overlays** (DOM within the transparent ghost window) can be positioned freely but suffer from the bleed problem above (fixable with nudge), BUT require a much larger transparent window to have space for overlays (bubble above ghost, chat input below). This larger window blocks clicks on everything behind the transparent area since `setIgnoreCursorEvents` is all-or-nothing — there is no per-element hit-testing on transparent windows.

**Current decision:** Chat input and chat bubble use overlays within the transparent ghost window (with nudge on dismiss to handle bleed). Settings and skin picker remain as separate opaque windows since they don't need precise positioning. The click-through problem on the enlarged transparent canvas remains unsolved.

**Rules:**
- Use separate opaque windows for complex UI panels (settings, skin picker) that don't need precise positioning
- Chat input and chat bubble must be overlays in the transparent ghost window — use the size nudge on dismiss to handle bleed
- Never use opacity transitions on transparent windows
- `setIgnoreCursorEvents` is all-or-nothing for the entire window — no per-element control
- Call `window.setFocus()` after showing a window that needs keyboard input
- Separate windows are opaque (`transparent: false`), hidden by default (`visible: false`), shown/hidden via `win.show()`/`win.hide()`
- Inter-window communication uses Tauri events, not shared React state

### Platform-Specific Window Positioning

Wayland compositors do not allow clients to set window positions programmatically — the compositor controls placement. To support multiple desktop environments, window positioning is abstracted through `app/src/lib/moveWindow.ts` and the Rust `move_window` command (`app/src-tauri/src/commands/window.rs`).

- **Sway**: Uses `swaymsg '[title="^..."] move position X Y'` to position windows via the compositor. Window titles in `tauri.conf.json` are prefixed with `ukagaka-` to enable unique targeting (e.g., `ukagaka-input`, `ukagaka-bubble`, `ukagaka-ghost`).
- **Fallback** (X11, unknown compositors): Falls back to Tauri's built-in `win.setPosition()`.
- **Adding new compositors**: Add detection (env var check) and positioning logic in `window.rs`. E.g., Hyprland via `hyprctl`, KDE via `kdotool`, etc.
- Always call `moveWindow(win, x, y)` or `moveWindowPhysical(win, x, y)` instead of `win.setPosition()` directly.

### i3/Tiling WM Gotchas

- **`setSize` is ignored for tiled windows.** All app windows must be floating (`for_window [app_id="..."] floating enable` in i3/Sway config).

### Multi-Window Keyboard Events

- Use `keydown` (not `keyup`) for keyboard shortcuts in the main ghost window. When a popup window (e.g., chat-input) handles `keydown` and hides itself, the orphaned `keyup` propagates to the main window after focus returns. Using `keydown` avoids this because each OS window receives its own `keydown`.
- When a popup closes by sending an event (e.g., `chat-send`), the main window's event listener fires before the stale keyup — so event-driven close paths don't have this problem. But dismiss-only paths (empty Enter, ESC) do.

### GTK Minimum Window Size

GTK enforces a minimum window size (~100-150px height). You cannot make a window smaller. Workaround: make the window transparent and use `alignItems: 'flex-end'` in CSS to anchor visible content at the bottom of the oversized transparent window. Always query `win.outerSize()` for the actual size after `setSize()` — don't assume the requested size was honored.

### Save-on-Exit Resilience

When saving state before exit (e.g., window position), always wrap the save in a try-catch so the app exits even if saving fails (disk full, permissions, etc.). The Rust tray exit handler is safe because `app.exit(0)` runs unconditionally. The frontend `savePositionAndExit()` must catch errors from `invoke('set_ghost_position')`.

### Tauri Capabilities

Permissions are in `app/src-tauri/capabilities/default.json`. If adding new Tauri APIs (e.g., shell, dialog, notification), add the corresponding permission there.

## Remaining Work

See `TODO.md` for the full list. Key items:
- Real character artwork (currently placeholder colored circles)
- Live gateway testing (built against protocol spec, not yet tested against running OpenClaw)
- Hit-testing validation on X11/Wayland
- System prompt configuration for expression tags
- Cross-platform builds (macOS, Windows)

## Debugging

src-tauri/src/lib.rs has `debug_log()` in case you cant open the Ctrl+Shift+I web debug console - you can't open it sometimes!
