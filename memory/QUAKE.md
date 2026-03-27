# Quake-Style Dropdown Terminal

## What It Is

A quake/yakuake-style dropdown terminal toggled by a global hotkey or SIGUSR1 signal. Spawns an external terminal emulator at the top of the screen, full width, ~40% height. Runs `openclaw tui` by default. The terminal process persists in the background when hidden.

## Architecture

The quake terminal is **not** a Qt window. It is an external terminal emulator process managed entirely from Python. This keeps it decoupled from the PySide6 window system.

### Implementation (`app/src/lib/quake_terminal.py`)

`QuakeTerminalManager(QObject)` manages:
- Terminal auto-detection and spawning via `subprocess.Popen`
- Show/hide via compositor-specific commands (`swaymsg` or `xdotool`)
- SIGUSR1 signal handler for Wayland-compatible hotkey toggle
- Process lifecycle (liveness checks, cleanup on exit)

Signals:
- `toggled(bool)` — emitted after toggle with new visibility state
- `toggle_requested()` — emitted from SIGUSR1 polling, connected to toggle handler

### Keyboard Shortcut (SIGUSR1 Approach)

Wayland compositors don't allow applications to grab global hotkeys — there is no protocol for it.

**Solution:** DeskMate registers a Unix signal handler for `SIGUSR1` at startup. A `QTimer` polls a `threading.Event` every 100ms; when the signal is received, it emits `toggle_requested` on the Qt main thread. Users bind a key in their compositor config:

```
# Sway / i3
bindsym Mod4+grave exec pkill -USR1 -x python3

# Hyprland
bind = SUPER, grave, exec, pkill -USR1 -x python3
```

**Why SIGUSR1:** Zero dependencies, no port conflicts, works identically on X11 and Wayland, 100ms latency is imperceptible.

### Config

In `~/.config/deskmate/config.yaml` under `quake_terminal:`:

```yaml
quake_terminal:
  enabled: true
  hotkey: ctrl+alt+`             # informational; actual toggle is via SIGUSR1 or tray menu
  terminal_emulator: null         # null = auto-detect; or "foot", "kitty", etc.
  command: openclaw tui
  height_percent: 40
```

### Terminal Detection Priority

| Platform | Priority List | Fallback |
|----------|--------------|----------|
| Linux | foot, kitty, alacritty, konsole, xterm, xfce4-terminal | None (error) |
| macOS | iTerm2, kitty, alacritty | Terminal.app |
| Windows | wt (Windows Terminal) | powershell |

Detection uses `shutil.which()` to probe PATH. User can override via `terminal_emulator` config.

### Toggle Logic

1. **Always check process liveness first** — `process.poll()` on the stored `Popen`. If process exited (user closed terminal, command finished), reset state.
2. **No process**: detect terminal, get screen geometry via `QApplication.primaryScreen()`, spawn with terminal-specific flags and `--title deskmate-quake`.
3. **Process alive**: toggle visibility via platform-specific show/hide.

### Show/Hide Mechanisms

| Platform | Hide | Show |
|----------|------|------|
| Sway | `swaymsg '[title="^deskmate-quake$"] move position 0 -9999'` | `swaymsg '[title="^deskmate-quake$"] move position 0 0, resize set W H, focus'` |
| X11 | `xdotool search --name deskmate-quake windowunmap` | `xdotool search --name deskmate-quake windowmap windowactivate` |

Compositor detection via environment variables: `SWAYSOCK` (Sway), `HYPRLAND_INSTANCE_SIGNATURE` (Hyprland).

### Window Identification

Terminals are spawned with `--title deskmate-quake` (or equivalent flag). Show/hide commands target this title. All terminals in the detection priority list support title flags.

### Integration (`app/main.py`)

- Created in `DeskMate.__init__()`, signals connected
- `toggle_requested` signal → `_toggle_quake_terminal()` (SIGUSR1 path)
- Tray menu "Toggle Terminal" → `_toggle_quake_terminal()`
- `_quit()` calls `quake.cleanup()` to kill terminal process

### Exit Cleanup

Terminal process is killed on app exit via `process.terminate()` in `cleanup()`. Wrapped in try/except so app exits cleanly even if the process is already dead.

## Known Limitations

- **Sway offscreen hide leaves a phantom in Alt+Tab** — the window is at y=-9999 but still in the compositor tree. Future fix: use `move scratchpad` instead.
- **macOS/Windows code paths are untested** — written from API docs.
- **No slide animation** — terminal appears/disappears instantly.
- **Hyprland/KDE/GNOME positioning not yet implemented** — would use `hyprctl`, `kdotool`, etc.

## Decision: Why External Process, Not Embedded Terminal

- Users get their preferred terminal emulator with their config (colors, fonts, shell)
- No pseudo-terminal complexity (xterm.js, etc.)
- Terminal process is fully independent — crash isolation
- Simpler implementation: spawn, show, hide, kill
