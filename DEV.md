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
  manifest.json     # { name, author, version, expressions: { happy: "happy.png", ... } }
  happy.png
  sad.png
  angry.png
  disgusted.png
  condescending.png
  thinking.png
  uwamezukai.png
  neutral.png
```

### Expression System

Expressions are parsed client-side from AI text using `[expression:X]` tags, then stripped from display. Falls back to `neutral`. The AI agent must be prompted to emit these tags — there is no protocol-native expression field.

Valid expressions: `happy`, `sad`, `angry`, `disgusted`, `condescending`, `thinking`, `uwamezukai`, `neutral`

### Tauri Capabilities

Permissions are in `app/src-tauri/capabilities/default.json`. If adding new Tauri APIs (e.g., shell, dialog, notification), add the corresponding permission there.

### Asset Protocol

Local files (skin PNGs) are served to the webview via Tauri's asset protocol. Configured in `tauri.conf.json` under `app.security.assetProtocol`. The scope must cover the paths returned by the skin loader. In dev mode, skins are at an absolute filesystem path; in production, they're under `$RESOURCE/skins/`.
