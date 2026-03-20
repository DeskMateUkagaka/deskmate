# DEV.md — Developer Guide

## Prerequisites

- **Rust** (stable, ≥1.77.2): https://rustup.rs
- **Node.js** (≥18)
- **pnpm**: `npm i -g pnpm`
- **Tauri CLI v2**: `cargo install tauri-cli --version "^2"`
- **Linux system deps** (Debian/Ubuntu):
  ```bash
  sudo apt install libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev
  ```
  Arch:
  ```bash
  sudo pacman -S webkit2gtk-4.1 gtk3 libayatana-appindicator librsvg
  ```

## Getting Started

```bash
cd app
pnpm install          # install frontend dependencies
cargo tauri dev       # starts Vite + Tauri with hot reload
```

Rust dependencies are fetched automatically by Cargo on first build.

## Build Commands

All commands run from the `app/` directory:

```bash
cargo tauri dev           # dev mode with hot reload
cargo tauri build         # production build (binary + .deb + .rpm)
npx tsc --noEmit          # TypeScript check only
cargo check               # Rust check only (from app/src-tauri/)
pnpm add <package>        # add frontend dependency
cargo add <crate>         # add Rust dependency (from app/src-tauri/)
```

## Debugging

- **Webview devtools**: Press `Ctrl+Shift+I` while the app is focused
- **Rust logs**: Appear in the terminal where `cargo tauri dev` is running
- **JS console.log**: Goes to the webview devtools console, NOT the terminal

## Debug Commands

Type these into the chat input to test features without a gateway connection:

- **`ack`** — Returns "ACK" after a brief simulated stream. Tests basic bubble display.
- **`emo`** — Picks a random non-neutral emotion from the current skin and displays it. Tests emotion switching, dismiss→neutral revert, and pin→persist behavior.
- **`md`** — Returns a rich Markdown sample (headers, bold, code block, list, blockquote, table, link). Tests Markdown rendering, syntax highlighting, and bubble theming.

## Known Platform Issues

### NVIDIA GPU: `Failed to create GBM buffer`

WebKitGTK + NVIDIA proprietary drivers have a known issue with DMA-BUF allocation for transparent windows. Fix:

```bash
WEBKIT_DISABLE_COMPOSITING_MODE=1 cargo tauri dev
```

Other env vars that may help:
```bash
WEBKIT_DISABLE_DMABUF_RENDERER=1 cargo tauri dev
```

### Sway / Wayland

The app works on Sway with the `WEBKIT_DISABLE_COMPOSITING_MODE=1` workaround above. XWayland is used when `GDK_BACKEND=x11` is set (usually enabled in Sway by default).

## Architecture Overview

### Two-Layer System
- **Rust backend** (`app/src-tauri/src/`): Tauri commands, OpenClaw WebSocket client, skin loader, settings persistence
- **React frontend** (`app/src/`): Components + hooks calling Rust via `invoke()`, Tauri events for streaming

### Data Flow

```
User types → ChatInput → invoke('chat_send') → Rust GatewayClient → OpenClaw WS
OpenClaw WS → Rust EventFrame listener → app.emit("chat-event") → useOpenClaw hook → Bubble
```

### Key Files

| Area | File |
|------|------|
| App entry | `app/src/App.tsx` |
| Ghost character | `app/src/components/Ghost.tsx` |
| Chat hook | `app/src/hooks/useOpenClaw.ts` |
| Skin hook | `app/src/hooks/useSkin.ts` |
| Settings hook | `app/src/hooks/useSettings.ts` |
| Rust gateway client | `app/src-tauri/src/openclaw/client.rs` |
| Rust chat commands | `app/src-tauri/src/commands/chat.rs` |
| Skin loader | `app/src-tauri/src/skin/loader.rs` |
| Settings persistence | `app/src-tauri/src/settings/store.rs` |
| Tauri capabilities | `app/src-tauri/capabilities/default.json` |
| Tauri config | `app/src-tauri/tauri.conf.json` |

### Skin Format

Each skin is a folder under `app/skins/`:
```
skins/<skin-id>/
  manifest.yaml     # { name, author, version, emotions: { happy: "happy.png", ... } }
  happy.png
  sad.png
  angry.png
  disgusted.png
  condescending.png
  thinking.png
  uwamezukai.png
  neutral.png
```

### Emotion System

Emotions are parsed client-side from AI text using `[emotion:X]` tags, then stripped from display. Falls back to `neutral`. The AI agent must be prompted to emit these tags — there is no protocol-native emotion field.

Available emotions are **dynamic per skin** — defined in the skin's `manifest.yaml` `emotions` map. The only required emotion is `neutral` (all skins must have it). When the AI sends an unknown emotion, it falls back to `neutral` with a warning logged.

When the bubble is dismissed (manually or by auto-dismiss timer), the ghost reverts to `neutral`. When the bubble is pinned, the ghost stays in the current emotion until the user manually dismisses it.

### Tauri Capabilities

Permissions are in `app/src-tauri/capabilities/default.json`. If adding new Tauri APIs (e.g., shell, dialog, notification), add the corresponding permission there.

## E2E Tests (Window Positioning & Bleed Detection)

Automated integration tests that launch the real app on Sway Wayland and verify window positioning correctness and transparency bleed absence. These are **not unit tests** — they interact with the live compositor.

### Design Decisions

- **Rust integration tests** (`app/src-tauri/tests/`) using `swayipc` for compositor queries and `grim` for screenshots. No browser automation (Playwright/Cypress) — the testable behavior is at the compositor level, not the DOM.
- **Bleed detection** via screenshot comparison: a green `(0,255,0)` background is rendered via `swaybg` on the wallpaper layer. After hiding UI elements, the region is screenshotted and all pixels are verified to be green within ±5 per RGB channel. Non-green pixels = stale bleed artifacts.
- **Position verification** via `swayipc::get_tree()`: query the compositor for actual window coordinates, compare against expected within ±5px. No screenshot alignment or template matching needed.
- **Sway only** for now — the only platform with compositor IPC implemented. Tests skip automatically on non-Sway environments.
- **Sequential execution** (`--test-threads=1`) because tests manipulate global compositor state.

### System Dependencies

```bash
# Arch Linux
sudo pacman -S grim swaybg wtype
```

- `grim` — Wayland screenshot tool
- `swaybg` — solid-color wallpaper for green-screen bleed detection
- `wtype` — Wayland keyboard simulation (replaces xdotool)

### Running

```bash
# 1. Build the app binary (once)
cd app && cargo tauri build --debug

# 2. Run E2E tests (must be on a Sway session)
cd app/src-tauri && cargo test --test e2e -- --test-threads=1
```

Tests skip with a message if `SWAYSOCK` is not set (i.e., not on Sway).

### Test Scenarios

| File | Tests | What it verifies |
|------|-------|-----------------|
| `ghost_window.rs` | Ghost renders, transparent background, position save/restore | Ghost appears in Sway tree, corners are transparent (green), Ctrl+Q saves position and relaunch restores it |
| `popup_position.rs` | Input/bubble positioned near ghost, show-before-move regression | Popups appear near the ghost (not at 0,0), catching the "hidden windows can't be moved on Sway" bug |
| `bleed.rs` | No bleed after bubble hide, no bleed after input hide | After dismissing a popup, screenshot its former region — all pixels must be green (no stale artifacts) |
| `keyboard.rs` | Focus returns after input close | After closing the chat input with Escape, ghost window gets focus back |

### Test Infrastructure

```
app/src-tauri/tests/
  e2e.rs                    # entry point
  helpers/
    app.rs                  # launch/kill app binary (DESKMATE_TEST_MODE=1, isolated data dir)
    sway.rs                 # swayipc wrappers: find_window, wait_for_window, assert_position_near, send_key
    screenshot.rs           # grim capture + green pixel verification
    green_screen.rs         # swaybg launcher (green wallpaper), killed on Drop
  tests/
    ghost_window.rs
    popup_position.rs
    bleed.rs
    keyboard.rs
```

The `DESKMATE_TEST_MODE=1` env var enables `e2e_inject_event` — a Tauri command that emits arbitrary events, allowing tests to simulate chat responses without a gateway connection.

### Asset Protocol

Local files (skin PNGs) are served to the webview via Tauri's asset protocol. Configured in `tauri.conf.json` under `app.security.assetProtocol`. The scope must cover the paths returned by the skin loader. In dev mode, skins are at an absolute filesystem path; in production, they're under `$RESOURCE/skins/`.
