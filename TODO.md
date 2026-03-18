# Ukagaka v1 TODO

## Immediate Product Gaps

- [ ] Copy text from the bubble
  - [x] Ctrl+C with selection works
  - [ ] Ctrl+C without selection won't work
  - [ ] Can't select the code block to copy
- [ ] Add a conversation history / quake-style terminal window
- [ ] Add a global shortcut to show/hide the ghost
- [ ] Add an actual poke reaction for middle-click instead of just logging `poke!`
- [ ] Add idle animation / neutral variation when the character is not speaking
- [ ] Distinguish proactive dialogue visually from normal replies
- [ ] Persist the last-used session key instead of always using `main`
- [ ] Add a session picker UI backed by `list_sessions`
- [ ] Add command autocomplete in the chat input
- [ ] Turn the existing token field into a proper first-run setup flow

## Runtime Verification

- [x] Test against a live OpenClaw gateway (challenge/nonce handshake, token auth)
- [x] Test Wayland transparency (`GDK_BACKEND=wayland`)
- [x] Verify `[emotion:X]` prompting end-to-end with actual model responses
- [x] Decide where the `[emotion:X]` contract should be injected: `chat.inject`, agent config, or per-message prelude

## Platform Test Matrix

### Linux - Sway (Wayland)

- [x] Transparent ghost window renders correctly with the WebKitGTK workaround
- [x] Popup positioning works via `swaymsg` compositor IPC
- [x] Hidden popup windows are shown before being moved
- [x] Floating-window rule requirement is documented
- [x] Bubble repaint nudge workaround is in place for transparency bleed
- [x] Save/restore ghost position after drag
- [ ] Bubble stays correctly anchored after repeated drags

### Linux - X11 + i3

- [ ] Floating-window rule requirement works in practice
- [ ] Ghost drag updates and persists position correctly
- [ ] Restart restores the saved ghost position
- [ ] Tauri fallback window positioning behaves correctly on X11
- [ ] Bubble and chat-input positioning remain correct after multiple drags

### Linux - Hyprland (Wayland)

- [ ] Implement compositor-specific window positioning
- [ ] Transparent ghost window renders correctly
- [ ] Floating-window rules behave correctly
- [ ] Ghost drag updates and persists position correctly
- [ ] Restart restores the saved ghost position
- [ ] Bubble and chat-input placement work after repeated drags

### Linux - KDE Plasma Wayland

- [ ] Implement compositor-specific window positioning
- [ ] Transparent ghost window renders correctly
- [ ] Window rules for floating / always-on-top work correctly
- [ ] Ghost drag updates and persists position correctly
- [ ] Restart restores the saved ghost position
- [ ] Multi-monitor placement behaves correctly

### Linux - GNOME / Mutter Wayland

- [ ] Implement compositor-specific window positioning
- [ ] Transparent ghost window renders correctly
- [ ] Always-on-top behavior works with GNOME tooling or extensions
- [ ] Ghost drag updates and persists position correctly
- [ ] Restart restores the saved ghost position
- [ ] Bubble and popup focus behavior remain correct

### macOS

- [ ] App builds successfully
- [ ] Transparent ghost window renders correctly
- [ ] Tray icon behavior works correctly
- [ ] Ghost drag updates and persists position correctly
- [ ] Restart restores the saved ghost position
- [ ] Bubble, settings, and chat-input windows position correctly
- [ ] Multi-monitor placement behaves correctly

### Windows

- [ ] App builds successfully
- [ ] Transparent ghost window renders correctly
- [ ] Tray icon behavior works correctly
- [ ] Ghost drag updates and persists position correctly
- [ ] Restart restores the saved ghost position
- [ ] Bubble, settings, and chat-input windows position correctly
- [ ] Multi-monitor placement behaves correctly

### Cross-Platform Windowing Regressions

- [ ] Dragging the ghost does not break later popup positioning
- [ ] Ghost position survives normal exit and restart
- [ ] Save-on-exit failure does not block app shutdown
- [ ] HiDPI coordinate conversions stay correct across drag, restore, and popup placement
- [ ] Transparent-window repaint workaround still clears bleed after show/hide cycles
- [ ] Keyboard focus returns to the correct window after popup close

## Art And Content

- [ ] Commission or create real character art (7 expression PNGs per skin)
- [ ] Decide production character PNG resolution / default window size
- [ ] Replace placeholder default skin artwork with final art
- [ ] Create at least 2 real skins to test switching and packaging
- [ ] Replace the default tray icon artwork

## Platform And Packaging

- [ ] Add real multi-monitor support instead of relying on `window.screen`
- [ ] Test Linux Wayland compositors beyond Sway and implement compositor-specific window movement where needed
- [ ] Implement Hyprland window positioning in the Rust window command
- [ ] Test tiling WM requirements and document any remaining floating-window rules
- [ ] Build and test on macOS
- [ ] Build and test on Windows
- [ ] Fix AppImage bundling

## Gateway And Protocol Follow-ups

- [ ] Build a mock WebSocket server for offline development/testing
- [ ] Exercise reconnection and exponential backoff against a real gateway failure/recovery cycle
- [ ] Test `chat_abort` against a real in-flight run
- [ ] Verify `idempotencyKey` behavior on reconnect/retry paths
- [ ] Verify `seq` ordering assumptions for streaming deltas
- [ ] Decide whether action buttons should stay hardcoded or move to a protocol extension later

## Housekeeping

- [ ] Set the Buy Skins URL
- [ ] Replace the default app icons
- [ ] Expand the top-level README into a user-facing setup guide
- [ ] Document skin creation for community authors

## Later / v2

- [ ] Protocol-native emotion/expression field instead of tag parsing
- [ ] AI-decided action buttons via protocol extension
- [ ] Device identity auth (key-pair signing, nonce binding)
- [ ] Animated expression transitions
- [ ] Sidekick / kero character
- [ ] Steam Workshop skin upload/download
- [ ] Voice output / TTS

## Already Landed In Code

- [x] Tray icon with show/hide, Change Skin, Settings, and Exit
- [x] Bubble lifetime UX: countdown progress bar, pin, dismiss with `x` / `Escape`
- [x] Bubble edge clamping with content offset compensation near screen edges
- [x] Dynamic ghost window sizing from skin image dimensions
- [x] Settings stored in `config.yaml`
- [x] Gateway URL/token editable from the Settings window
- [x] Backend support for `chat_abort`
- [x] Reconnection loop with exponential backoff in the gateway client
- [x] Bubble Markdown rendering with themed code blocks
