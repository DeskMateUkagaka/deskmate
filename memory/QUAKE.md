# Quake-Style Dropdown Terminal

## What It Is

A quake/yakuake-style dropdown terminal toggled by a global hotkey (default: Ctrl+Alt+`). Spawns an external terminal emulator at the top of the screen, full width, ~40% height. Runs `openclaw tui` by default. The terminal process persists in the background when hidden.

## Architecture

The quake terminal is **not** a Tauri window. It is an external terminal emulator process managed entirely from Rust. This keeps it decoupled from the existing Tauri window system (moveWindow.ts, resizeWindow.ts, popup positioning).

### Module Structure

```
app/src-tauri/src/quake_terminal/
  mod.rs      — QuakeTerminalState (process handle, visibility, terminal name)
  detect.rs   — Platform-specific terminal auto-detection
  spawn.rs    — Per-terminal spawn commands + Sway positioning via swayipc
  toggle.rs   — Toggle logic with process liveness checks, show/hide
```

### State Management

`QuakeTerminalState` is managed via `Arc<Mutex<>>` (same pattern as `GatewayState` and `ProactiveState`). Registered in `lib.rs` setup.

### Keyboard Shortcut (Two-Layer Approach)

Wayland compositors don't allow applications to grab global hotkeys — there is no protocol for it. The `tauri-plugin-global-shortcut` plugin relies on X11's `XGrabKey`, which doesn't work on native Wayland sessions (Sway, Hyprland, etc.). This means the `hotkey` field in `config.yaml` only works on X11.

**Solution: SIGUSR1 signal handler.** DeskMate registers a Unix signal handler for `SIGUSR1` at startup (`lib.rs`). A background thread polls an `AtomicBool` every 100ms; when the signal is received, it toggles the quake terminal. Users bind a key in their compositor config to send the signal:

```
# Sway / i3
bindsym Mod4+grave exec pkill -USR1 -x deskmate

# Hyprland
bind = SUPER, grave, exec, pkill -USR1 -x deskmate
```

**Why SIGUSR1 and not sockets/DBus:**
- Zero dependencies — `libc::signal` is trivial, no runtime or listener setup
- No port conflicts, no file cleanup on crash
- `pkill -USR1 -x deskmate` is a one-liner users can bind in any WM
- The 100ms polling latency is imperceptible

**Why not fix global-shortcut on Wayland:**
- Wayland has no global hotkey protocol by design (security model)
- Some compositors have proprietary extensions (Sway has none for this)
- The signal approach works identically on X11, Wayland, and headless

**Implementation details:**
- Signal handler (`extern "C" fn`) only sets an `AtomicBool` — async-signal-safe
- Polling thread sleeps 100ms between checks (negligible CPU)
- Thread holds a cloned `AppHandle` to access `QuakeTerminalState` and `Settings`
- The `tauri-plugin-global-shortcut` registration is still attempted (works on X11) and is wrapped in a labeled block (`'quake: { ... }`) so any error logs and breaks out without crashing

### Config

In `config.yaml` under `quake_terminal:`:

```yaml
quake_terminal:
  enabled: true
  hotkey: ctrl+alt+`             # only works on X11; Wayland users bind via compositor
  terminal_emulator: null         # null = auto-detect; or "foot", "kitty", etc.
  command: openclaw tui
  height_percent: 40
```

Rust struct: `settings::QuakeTerminalConfig` (in `settings/store.rs`). TypeScript: `QuakeTerminalConfig` (in `types/index.ts`). Both must stay in sync.

Hotkey format follows `global-hotkey` crate syntax: `ctrl+alt+\``, `CommandOrControl+Shift+A`, etc.

### Terminal Detection Priority

| Platform | Priority List | Fallback |
|----------|--------------|----------|
| Linux | foot, kitty, alacritty, konsole, xterm, xfce4-terminal | None (error) |
| macOS | iTerm2, kitty, alacritty | Terminal.app (always available) |
| Windows | wt (Windows Terminal) | powershell |

Detection uses `which` (Linux/macOS) or `where` (Windows) to probe PATH.

### Toggle Logic

1. **Always check process liveness first** — `try_wait()` on the stored `Child`. If process exited (user closed terminal, command finished), reset state.
2. **No process**: detect terminal, get screen geometry via Tauri monitor API, spawn with positioning.
3. **Process alive**: toggle visibility via platform-specific show/hide.

This avoids the "zombie toggle" bug where pressing the hotkey tries to hide a dead process.

### Show/Hide Mechanisms

| Platform | Hide | Show |
|----------|------|------|
| Sway | `swayipc` `run_command`: `[title="^deskmate-quake$"] move position 0 -9999` | `[title="^deskmate-quake$"] move position 0 0, resize set W H` + `focus` |
| X11 | `xdotool search --name "deskmate-quake" windowunmap` | `xdotool search --name "deskmate-quake" windowmap windowactivate` |
| macOS | AppleScript: set visible of process to false | AppleScript: activate + set bounds |
| Windows | Windows Terminal has built-in quake mode | WT quake mode handles toggle natively |

**Important:** All Sway IPC uses the `swayipc` Rust crate (`Connection::new()` + `run_command()`), NOT the `swaymsg` CLI binary. This matches the pattern in `commands/window.rs:44-75`.

### Window Identification

Terminals are spawned with `--title deskmate-quake` (or equivalent flag). Sway/X11 show/hide commands target this title. If a terminal doesn't respect `--title`, the show/hide mechanism breaks. All terminals in the detection priority list support `--title`.

### Known Limitations

- **Sway offscreen hide leaves a phantom in Alt+Tab** — the window is at y=-9999 but still in the compositor tree. Acceptable for v1. Future fix: hybrid scratchpad approach (`move scratchpad` to hide, explicit `move position` to show).
- **macOS/Windows code paths are untested** — written from API docs, gated with `#[cfg(target_os)]`. Stub-quality until tested on those platforms.
- **No slide animation** — terminal appears/disappears instantly.
- **Spawn positioning on Sway needs retry** — newly spawned windows may not be in the compositor tree immediately. `spawn.rs::sway_position_terminal()` retries up to 10 times with 100ms async sleep, matching the pattern in `commands/window.rs:47-73`.

### Exit Cleanup

Terminal process is killed on app exit via the `exit_app` Tauri command in `commands/ghost.rs` — uses `app.try_state()` (not `State<>` injection) so it works even if the quake feature failed to initialize. The tray menu emits a `menu-action` event to the frontend, which calls `savePositionAndExit()` → `invoke('exit_app')`.

Both paths use `child.kill()` wrapped in `let _ =` to ignore errors.

### Tauri Commands (Frontend Integration)

- `toggle_quake_terminal` — programmatic toggle (e.g., from a UI button)
- `get_quake_terminal_status` — returns `bool` visibility state
- `quake-terminal-error` event — emitted on toggle failure, can be listened to in frontend

### Dependencies Added

- `tauri-plugin-global-shortcut = "2"` in `Cargo.toml` (X11 hotkey, no-op on Wayland)
- `libc` in `Cargo.toml` (SIGUSR1 signal handler)
- `"global-shortcut:default"` permission in `capabilities/default.json`

### Key API Gotchas (tauri-plugin-global-shortcut v2.3.1)

- `ShortcutEvent` is a struct with a `.state` field (not an enum with `Pressed` variant)
- Use `event.state == ShortcutState::Pressed` to check for key press
- `Shortcut` type is re-exported from `global-hotkey` crate as `HotKey`
- Must type-annotate when parsing: `let shortcut: Shortcut = config.hotkey.parse()?`
- Plugin must be registered with `.with_handler()` in one place — do NOT register the plugin separately then try to add a handler later

### Decision: Why External Process, Not Embedded Terminal

- Users get their preferred terminal emulator with their config (colors, fonts, shell)
- No pseudo-terminal complexity (xterm.js, etc.)
- Terminal process is fully independent — crash isolation
- Simpler implementation: spawn, show, hide, kill

### Decision: Why Global Hotkey, Not App-Level Key

App-level keydown only works when the ghost window has focus. Once the terminal is visible and focused, the ghost can't hear keystrokes. There is no way to dismiss the terminal without a global hotkey. This is how every shipping quake terminal (Yakuake, Guake, Tilda) works.

## Files

| File | Role |
|------|------|
| `src-tauri/src/quake_terminal/mod.rs` | State struct |
| `src-tauri/src/quake_terminal/detect.rs` | Terminal detection |
| `src-tauri/src/quake_terminal/spawn.rs` | Terminal spawning + Sway positioning |
| `src-tauri/src/quake_terminal/toggle.rs` | Toggle logic + show/hide |
| `src-tauri/src/commands/quake_terminal.rs` | Tauri commands |
| `src-tauri/src/settings/store.rs` | `QuakeTerminalConfig` struct |
| `src-tauri/src/lib.rs` | Plugin + hotkey registration, exit cleanup |
| `src-tauri/src/commands/ghost.rs` | `exit_app` terminal cleanup |
| `src-tauri/capabilities/default.json` | `global-shortcut:default` permission |
| `src/types/index.ts` | `QuakeTerminalConfig` TypeScript interface |
