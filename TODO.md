# DeskMate v1 TODO

## Immediate Product Gaps

- [x] Get Skins
- [ ] Add a conversation history / quake-style terminal window
  - [x] Use real terminal? Like, foot terminal?
  - [ ] How about Mac?
  - [ ] What happens on Windows?
- [ ] Write README
- [ ] Installation instructions
  - [ ] Human part - need a bootstrap before the AI can handle stuff on its own
  - [ ] AI part
- [ ] Set up PyInstaller or Briefcase packaging (Linux AppImage, Windows .exe, macOS .app)
  - Options: PyInstaller (most common), Nuitka (compiled), Briefcase (single config)
  - Build on each platform separately (no cross-compilation)

## Runtime Verification

- [x] Test against a live OpenClaw gateway (challenge/nonce handshake, token auth)
- [x] Verify `[emotion:X]` prompting end-to-end with actual model responses

## Later

- Claude Code Channels
  - [ ] let user choose the ghost engine - openclaw vs claude code
  - [ ] and let it control the side kick
- [ ] Easer Openclaw Setup:
  - [ ] Turn the existing token field into a proper first-run setup flow
- [ ] Actually make the e2e tests work
- [ ] Sidekick / kero character

## Even Later
- [ ] Voice output / TTS
- [ ] Bubble config - e.g., font and size
- [ ] Some voices (AI generated even!)
  - [ ] On click + text input open - says something, like RTS unit selection
  - [ ] Too many clicks in a short time window - gets annoyed, Warcraft style
- [ ] Animated expression transitions

## Platform Test Matrix

### Linux - Sway (Wayland)

- [x] Transparent ghost window renders correctly with the WebKitGTK workaround
- [x] Popup positioning works via `swaymsg` compositor IPC
- [x] Hidden popup windows are shown before being moved
- [x] Floating-window rule requirement is documented
- [x] Bubble repaint nudge workaround is in place for transparency bleed
- [x] Save/restore ghost position after drag
- [x] Bubble repositions correctly after repeated drags

### Linux - X11 + i3

- [ ] Floating-window rule requirement works in practice
- [ ] Ghost drag updates and persists position correctly
- [ ] Restart restores the saved ghost position
- [ ] Tauri fallback window positioning behaves correctly on X11
- [ ] Bubble repositions correctly after repeated drags

### Linux - Hyprland (Wayland)

- [ ] Implement compositor-specific window positioning
- [ ] Transparent ghost window renders correctly
- [ ] Floating-window rules behave correctly
- [ ] Ghost drag updates and persists position correctly
- [ ] Restart restores the saved ghost position
- [ ] Bubble repositions correctly after repeated drags

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

- [x] Commission or create real character art (7 expression PNGs per skin)
- [x] Decide production character PNG resolution / default window size
- [x] Replace placeholder default skin artwork with final art
- [x] Create at least 2 real skins to test switching and packaging
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

- [ ] Set the Get Skins URL
- [ ] Expand the top-level README into a user-facing setup guide
- [ ] Document skin creation for community authors

## Done

- [x] Tray icon with context menu
- [x] Bubble lifetime UX: countdown progress bar, pin, dismiss with `x` / `Escape`
- [x] Bubble edge clamping with content offset compensation near screen edges
- [x] Dynamic ghost window sizing from skin image dimensions
- [x] Settings stored in `config.yaml`
- [x] Gateway URL/token editable from the Settings window
- [x] Reconnection loop with exponential backoff in the gateway client
- [x] Bubble Markdown rendering with themed code blocks
- [x] Copy text from the bubble
  - [x] Ctrl+C with selection works
  - [x] Ctrl+C without selection won't work
  - [x] Can't select the code block to copy - progress bar rendering deselects it
  - [x] Copy button in the code blocks (Markdown)
- [x] Invisible bubble blocks my clicking - bubbles window sizes must match that of the visible size
- [x] Reconnect websocket - show "thinking" ghost while connecting
- [x] Add idle animation
- [x] AI-decided action buttons via protocol extension
- [x] Add command autocomplete in the chat input
- [x] cache /commands - it pollutes conv hist
- [x] Make get skins work
  - [x] Use preview.png - mandatory
  - [x] skin config persistence - after choose skin keep it in user config
- [x] Replace the default app icons
- [x] bubble/chat input margins: window add top/bottom/left/right margin (tray size/edge differences per user)

## Won't Do

- [x] Persist the last-used session key instead of always using `main`
  - [ ] Add a session picker UI backed by `list_sessions`
  - Nay, let's just use main all the time, I have no reason to use other session name for now
