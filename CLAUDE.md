# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

AI-powered desktop companion (DeskMate) built with Tauri v2. A transparent character sits on the desktop, connected to an OpenClaw AI gateway for chat, expression switching, and skin management.

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
2. Client builds a signed device identity payload (v3 format, Ed25519) using the nonce, then sends `connect` RPC with `ConnectParams` (client ID: `gateway-client`, mode: `ui`, protocol: 3, token auth, device identity). Without the device identity, the server strips all scopes and `chat.send` fails with "missing scope: operator.write".
3. Server responds with `HelloOk`. On first connect, the device must be paired (approved) on the gateway side.
4. `chat.send` returns immediate ack `{ runId, status: "started" }` — do NOT use `expectFinal`
5. AI responses stream as separate `chat` EventFrames with `state: delta|final|error|aborted`

Reference implementations in `openclaw/`:
- `scripts/dev/gateway-ws-client.ts` — minimal client
- `src/tui/gateway-chat.ts` — production chat client
- `src/gateway/protocol/schema/logs-chat.ts` — ChatSendParams + ChatEvent schemas

### Expression System

`ChatEventSchema` has NO `expression` field (`additionalProperties: false`). Expressions are parsed client-side from AI text content using `[expression:X]` tags, then stripped from display. Falls back to `neutral`. This is a known fragility — the AI must be prompted to emit these tags.

Valid expressions: `happy`, `sad`, `angry`, `disgusted`, `condescending`, `thinking`, `neutral`, `connecting`

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
  manifest.yaml     # { name, author, version, emotions: { happy: ["happy.png", ...], ... } }
  happy.png
  sad.png
  ...               # Each emotion can have multiple variant PNGs (random pick on change)
```

### Popup Window Positioning Coordinates

Bubble and input windows are positioned relative to the ghost image center on screen:
- `ghostPos` = ghost window's screen position (queried fresh from compositor via `getWindowPosition()`)
- `imageBounds` = ghost image bounds within the window (`centerX`, `centerY`, `top`, `bottom` in CSS pixels)
- `UiPlacement` (`x`, `y`, `margin_x`, `margin_y`) = skin-defined offset from image center
- **Always show before positioning** on Sway (`win.show()` then `moveWindow`) — hidden windows aren't in the compositor tree, so `swaymsg` can't target them. There may be a brief flash at the default position.
- **Coordinate spaces**: `windowPos` and `imageBounds` are in Sway layout coordinates (logical pixels). Tauri's `win.outerSize()` returns **physical pixels** — always divide by `win.scaleFactor()` before using in position calculations. Mixing physical and logical pixels causes mispositioned windows on HiDPI displays.

### Bubble Window Positioning (App.tsx → BubbleWindow.tsx)

The bubble is a fixed-size transparent window (648x548) with the visible bubble content inside. The visible content is much smaller than the window — positioning must account for both window placement AND content alignment within the window.

**Critical: window position ≠ content position.** The visible bubble content is aligned within the transparent window via CSS flexbox. Any feature that affects where the bubble appears on screen must coordinate BOTH the window position (App.tsx) and the content alignment within the window (BubbleWindow.tsx). Positioning only the window while content stays flex-centered will produce wrong visual results.

**Origin system** (`UiPlacement.origin`): determines which corner of the *visible content* the anchor point refers to. Values: `center` (default), `top-left`, `top-right`, `bottom-left`, `bottom-right`. Origin affects:
1. **Window position** (App.tsx): which corner of the window aligns with the anchor
2. **Content flex alignment** (BubbleWindow.tsx): `alignItems`/`justifyContent` match the origin corner so the visible content sits at the correct window corner
3. **Content offset clamping** (BubbleWindow.tsx): shift limits depend on which corner content is anchored to — content anchored at `flex-end` can shift toward `flex-start` but not further past the edge

**Stage 1 — Window positioning (App.tsx):**
1. Compute anchor: `anchorX = ghostPos.x + imageBounds.centerX + placement.x`
2. Apply origin offset to get window top-left: e.g., `bottom-right` → `idealX = anchorX - 648`
3. Clamp to screen edges: `screenX = clamp(idealX, margin_x, screenWidth - 648 - margin_x)`
4. Compute content offset: `contentOffsetX = idealX - screenX` (how far clamping shifted the window)
5. Emit `bubble-update` event with `contentOffsetX`/`contentOffsetY` and `origin` to BubbleWindow

**Stage 2 — Content alignment (BubbleWindow.tsx):**
1. Set flex alignment from origin (e.g., `bottom-right` → `alignItems: flex-end, justifyContent: flex-end`)
2. Receive `contentOffsetX`/`contentOffsetY` from App
3. Measure actual wrapper size via ref (`wrapperRef.current.offsetWidth`)
4. Clamp offset based on origin: content at `flex-start` can shift toward `flex-end` (full space), not past `flex-start` (0). Content at `center` can shift half the space each way.
5. Apply as `transform: translate(clampedX, clampedY)` on the bubble wrapper

This two-stage approach keeps the visible bubble aligned to the ghost even when the transparent window is clamped to a screen edge. Small bubbles (e.g., short "ACK" messages) shift more; wide bubbles filling the max width barely shift.

### Key State Management

- `GatewayState` (Rust): holds the WebSocket client, managed via `Arc<Mutex<>>`
- `ProactiveState` (Rust): holds the timer stop channel
- `Settings` (Rust): persisted to `$APP_DATA_DIR/settings.json`
- Frontend state: React hooks (`useOpenClaw`, `useBubble`, `useGhost`, `useSkin`, `useSettings`) — no external state library

### WebKitGTK Transparent Window Limitations (Linux)

WebKitGTK has a compositor bug where transparent windows leave ghost artifacts ("bleed") when DOM elements are removed or hidden. The upstream bug ([tauri#12800](https://github.com/tauri-apps/tauri/issues/12800)) was reportedly fixed in WebKitGTK 2.48.0, but bleed still occurs on WebKitGTK 2.50.5. This affects both X11 (i3) and Wayland (Sway) — it is a WebKitGTK issue, not compositor-specific.

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

**Ghost window nudge requires dual trigger (onLoad + useEffect fallback).** The ghost `<img>` expression change nudge in `Ghost.tsx` cannot be simplified to a single mechanism:
- **`onLoad`** provides correct paint timing (image is loaded and composited before nudge), but does NOT fire for cached images when `src` changes on the same `<img>` element in WebKitGTK.
- **`useEffect` on `imageSrc`** catches cached image changes that `onLoad` misses, but a nudge triggered ONLY from `useEffect` (even with `img.decode()` + double rAF) fires before the compositor has actually painted — the nudge repaints stale pixels.
- **Both are needed:** `onLoad` calls `runNudge()` for fresh loads; `useEffect` with `requestAnimationFrame` wrapper calls `runNudge()` as fallback for cached images, using `lastNudgedSrc` to skip if `onLoad` already handled it.
- Attempts that failed: `useEffect`-only with `setTimeout(150)`, `useEffect`-only with double rAF, `key={imageSrc}` to force DOM recreation (element destruction causes unfixable bleed), `win.hide()`/`win.show()` cycle.
- The `nudgeDirty` ref handles expression changes during an in-progress nudge (re-nudge after current cycle completes).

**Constraint: requires floating window.** On tiling WMs (Sway), `setSize` is ignored for tiled windows. The ghost window must be floating (`for_window [app_id="..."] floating enable` in Sway config).

**Why overlays were rejected:** Overlays (DOM within the transparent ghost window) avoid the Wayland positioning problem but require a much larger transparent window to contain the bubble, input, and ghost together. Most of that enlarged window is visually empty, yet it intercepts all clicks — the user clicks what looks like the desktop or another app, but the transparent window swallows the event. `setIgnoreCursorEvents` is all-or-nothing for the entire window, and forwarding click events to the app behind is non-trivial. This is unacceptable UX.

**Current decision:** All UI elements (chat bubble, chat input, settings, skin picker) use **separate windows**. Positioning on Wayland uses compositor-specific workarounds (`swaymsg` for Sway). The ghost window stays small (just the character image).

**Rules:**
- All popup UI (bubble, input, settings, skin picker) uses separate windows — never overlays in the ghost window
- Never use opacity transitions on transparent windows
- Call `window.setFocus()` after showing a window that needs keyboard input
- Separate windows are hidden by default (`visible: false`), shown/hidden via `win.show()`/`win.hide()`
- Inter-window communication uses Tauri events, not shared React state

### Platform-Specific Window Positioning

Wayland compositors do not allow clients to set window positions programmatically — the compositor controls placement. To support multiple desktop environments, window positioning is abstracted through `app/src/lib/moveWindow.ts` and the Rust `move_window` command (`app/src-tauri/src/commands/window.rs`).

- **Sway**: Uses `swaymsg '[title="^..."] move position X Y'` to position windows via the compositor. Window titles in `tauri.conf.json` are prefixed with `deskmate-` to enable unique targeting (e.g., `deskmate-input`, `deskmate-bubble`, `deskmate-ghost`).
- **Fallback** (X11, unknown compositors): Falls back to Tauri's built-in `win.setPosition()`.
- **Adding new compositors**: Add detection (env var check) and positioning logic in `window.rs`. E.g., Hyprland via `hyprctl`, KDE via `kdotool`, etc.
- Always call `moveWindow(win, x, y)` or `moveWindowPhysical(win, x, y)` instead of `win.setPosition()` directly.

### Wayland Window Position Tracking

- **`win.onMoved()` does NOT fire reliably on Wayland** — the compositor doesn't notify clients of position changes. Do not rely on it for tracking window position.
- Ghost position is tracked via `onPositionChange` callback from `Ghost.tsx` → `App.tsx`. Ghost reports its position on initial load (after `restoreWindowPosition`) and after each drag (after `startDragging` completes).
- Popup windows (bubble, input) compute their screen position from `windowPos` (ghost's compositor position) + `imageBounds` (ghost image bounds within the window) + skin `UiPlacement` offsets.
- **Hidden windows can't be moved on Sway** — they're not in the compositor tree, so `swaymsg` can't target them. Always `win.show()` before `moveWindow()`.

### i3/Tiling WM Gotchas

- **`setSize` is ignored for tiled windows.** All app windows must be floating (`for_window [app_id="..."] floating enable` in i3/Sway config).

### Multi-Window Keyboard Events

- Use `keydown` (not `keyup`) for keyboard shortcuts in the main ghost window. When a popup window (e.g., chat-input) handles `keydown` and hides itself, the orphaned `keyup` propagates to the main window after focus returns. Using `keydown` avoids this because each OS window receives its own `keydown`.
- When a popup closes by sending an event (e.g., `chat-send`), the main window's event listener fires before the stale keyup — so event-driven close paths don't have this problem. But dismiss-only paths (empty Enter, ESC) do.

### GTK Minimum Window Size

GTK enforces a minimum window size (200px height on current system, defined as `PLATFORM_MIN_WINDOW_HEIGHT` in `app/src/lib/resizeWindow.ts`). You cannot make a window smaller. Workaround: make the window transparent and use `alignItems: 'flex-end'` in CSS to anchor visible content at the bottom of the oversized transparent window.

### Window Resize Abstraction (`resizeWindow`)

Always use `resizeWindow(win, w, h)` from `app/src/lib/resizeWindow.ts` instead of `win.setSize()` directly. It:
1. Calls `setSize()` and waits for the compositor to process it (2 rAFs)
2. Queries `outerSize()` to get the **actual** size after GTK clamping
3. Returns `{ width, height }` in logical pixels
4. Warns when requested height is below `PLATFORM_MIN_WINDOW_HEIGHT`

**Always use the returned actual size for position calculations**, not the requested size — GTK clamping means the window may be larger than requested.

### Bubble Window Event Sequencing (Critical)

The bubble window lifecycle involves multiple async operations that must be carefully sequenced to avoid races:

1. **`nudgeWindowRepaint()`** (BubbleWindow) — reads `outerSize`, bumps +1px, waits, restores. Must fully complete before any content measurement, otherwise it overwrites subsequent `setSize` calls.
2. **`bubble-content-sized`** event (BubbleWindow → App) — measures visible content size. Must fire AFTER nudge completes (nudge restores the window to its pre-nudge size, and measurement reads `window.innerWidth/Height`).
3. **`resizeWindow` + `moveWindow`** (App positioning effect) — resizes to content size and repositions. Must use actual size from `resizeWindow` return value.

**Sequencing rule:** nudge → measure → emit content-sized → resize → reposition. Breaking this order causes the window to appear at wrong positions or sizes.

**Split effects rule:** The bubble popup has two separate effects in App.tsx:
- **Data emit effect** (synchronous): sends bubble data (items, theme, streaming state) to BubbleWindow via `bubble-update` event. Fires on every data change. Uses cached offsets from last positioning.
- **Positioning effect** (async): resizes and repositions the window. Only fires when `bubbleWindowSize` or `bubble.isVisible` changes. Stores computed offsets in a ref for the data effect to use.

Mixing async positioning into the data effect causes races — when multiple deps change in quick succession (e.g., streaming ends + content-sized arrives), multiple async IIFEs run concurrently and the last to finish wins, which may be a stale one.

**Known limitation: ack bubble flash.** Non-streaming (instant) responses cause the bubble to flash at 648x548 then shrink to content size ~500ms later when `bubble-content-sized` arrives. This is cosmetic and only affects non-streaming responses. Real LLM backends always stream, so the 648x548 window is correct — text fills it as it arrives. Not worth fixing.

### Save-on-Exit Resilience

When saving state before exit (e.g., window position), always wrap the save in a try-catch so the app exits even if saving fails (disk full, permissions, etc.). The Rust tray exit handler is safe because `app.exit(0)` runs unconditionally. The frontend `savePositionAndExit()` must catch errors from `invoke('set_ghost_position')`.

### Tauri Capabilities

Permissions are in `app/src-tauri/capabilities/default.json`. If adding new Tauri APIs (e.g., shell, dialog, notification), add the corresponding permission there.

## E2E Tests

Rust integration tests for window positioning and bleed detection on Sway. Uses `swayipc` for compositor queries, `grim` for screenshots, and a green-screen background for bleed detection. See `DEV.md` for full details, design decisions, and how to run them.

## Remaining Work

See `TODO.md` for the full list. Key items:
- Real character artwork (currently placeholder colored circles)
- Live gateway testing (built against protocol spec, not yet tested against running OpenClaw)
- Hit-testing validation on X11/Wayland
- System prompt configuration for expression tags
- Cross-platform builds (macOS, Windows)

## Debugging

**Always use `debugLog()` instead of `console.log()`** — `console.log` does not appear in WebKitGTK transparent windows even with web inspector open. Use the frontend helper `import { debugLog } from './lib/debugLog'` which writes to `/tmp/deskmate.log` via the Rust `debug_log` Tauri command. The Rust side is in `src-tauri/src/commands/ghost.rs`.

## Feature Documentation

Detailed design docs for implemented features live in `memory/`:
- `BTN.md` — Dynamic `[btn:msg]` button tags in AI chat responses
- `CmdAutoComplete.md` — Slash command autocomplete from gateway `/commands`
- `IDLE.md` — Idle animation system (RTS-style fidget clips)
- `QUAKE.md` — Quake-style dropdown terminal (Ctrl+Alt+` toggle, runs `openclaw tui`)
- `SKINS.md` — Skin format, community distribution, and skin picker

Read these before working on the relevant feature areas.

## VCS

* Always use `jj` (jujutsu) and never use `git` directly.
* After `jj desc` always run `jj new` to prevent changes mixing into the previous revision.
* When requested, uwe `jj workspace` to crete a separate workspace to work in parallel. (git equivalent of git worktree)
