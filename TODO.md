# Ukagaka v1 TODO

## Critical — Must Test Before First Real Use

- [x] Test against live OpenClaw gateway (challenge/nonce handshake, token auth)
- [x] Test Wayland transparency (`GDK_BACKEND=wayland`) — may need `gtk-layer-shell`
- [ ] Configure OpenClaw agent system prompt to emit `[expression:X]` tags
- [ ] Decide expression tag delivery method: `chat.inject` RPC, manual agent config, or prepend to each message
- [ ] Test with actual AI responses: verify expression parsing + stripping works end-to-end
- [x] Tray icon to show/hide on left click. Context menu on right click
- [ ] Quake terminal that shows all the conversations
- [ ] Global shortcut key that hides/shows the UI
- [ ] Investigate `outerPosition()` returning (0,0) on Sway/Wayland — ghost position not saved after drag
- [ ] Test under many desktop environments
  - [ ] X11 + i3
  - [ ] KDE Plasma Wayland
  - [ ] Sway
  - [ ] MacOS
  - [ ] Windows
- [ ] Idle animation - says nothing but sometimes a different neutral variation.

## Art & Assets

- [ ] Commission or create real character art (7 expression PNGs per skin)
- [ ] Decide character PNG resolution / window size (classic Ukagaka: ~200x400px)
- [ ] Replace placeholder colored-circle PNGs with actual artwork
- [ ] Create at least 2 skins to test skin switching
- [ ] Tray icon

## UX Polish

- [ ] Gateway token setup: add GUI (in Settings window or first-run flow) to let users paste their gateway token, instead of requiring manual settings.json editing
- [ ] Implement middle-click "poking" interaction (trigger character reaction, e.g. annoyed expression + bubble)
- [x] Add system tray icon (show/hide character, quit app)
- [ ] Handle multi-monitor: character stays on placed monitor
- [x] Bubble lifetime UX: 60s countdown progress bar, pin button, dismiss with `x` key, removed Expand
- [ ] Bubble positioning at screen edges (don't go off-screen)
- [ ] Resize window dynamically to fit character PNG dimensions
- [ ] Distinct visual style for proactive dialogue vs regular responses
- [ ] Persist last-used session key (currently always picks first session)
- [ ] Session selection dropdown in settings

## Platform Testing

- [ ] Test on Linux X11 (primary dev platform) — full functionality
- [ ] Test on Linux Wayland (Sway, Mutter, KWin) — transparency + always-on-top
- [ ] Test tiling WMs (i3, sway, Hyprland) — document float rule requirements
- [ ] macOS build + test (NSWindow transparency, notarization prep)
- [ ] Windows build + test (WS_EX_LAYERED, always-on-top behavior)
- [ ] Fix AppImage bundling (linuxdeploy issue)

## Gateway Integration

- [ ] Confirm local dev gateway auth mode (token vs none)
- [ ] Build mock WS server for offline development/testing
- [ ] Test WebSocket reconnection with exponential backoff
- [ ] Test `chat.abort` (cancel in-flight response)
- [ ] Verify `idempotencyKey` prevents duplicate sends on reconnect
- [ ] Verify seq-based ordering for streaming deltas

## Known Fragilities

- [ ] Expression tag parsing is fragile (AI may forget/misformat tags) — neutral fallback works but degrades UX
- [ ] Action buttons are hardcoded (no AI-decided buttons possible without protocol extension)
- [ ] Token-only auth (no device identity) — sufficient for local gateway, not for remote

## v2 Roadmap (not in scope now)

- [ ] Protocol-native expression field (requires OpenClaw PR to extend ChatEventSchema)
- [ ] AI-decided action buttons via protocol extension
- [ ] Device identity auth (key-pair signing, nonce binding)
- [ ] Animated expression transitions
- [ ] Sidekick/kero character (separate OpenClaw agent)
- [ ] Steam Workshop skin upload/download implementation
- [ ] Voice output / TTS
- [ ] Multi-window architecture (if hit-testing proves unreliable)

## Housekeeping

- [ ] Set "Buy Skins" URL (needs Steam store page or placeholder)
- [ ] Add app icon (replace Tauri default icons)
- [ ] Write user-facing README with setup instructions
- [ ] Document skin creation guide for community
