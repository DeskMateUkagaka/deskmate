# DeskMate

AI-powered desktop companion built with Tauri v2. A transparent character sits on your desktop, connected to an OpenClaw AI gateway for chat.

## Window Manager Configuration

The ghost window must be **floating** and **visible on all workspaces** (sticky) for proper behavior. Tiled mode breaks transparency, dismiss repaint, and positioning.

### Sway / i3

Add to your Sway or i3 config (`~/.config/sway/config` or `~/.config/i3/config`):

```
for_window [app_id="deskmate"] floating enable
for_window [app_id="deskmate"] sticky enable
```

Reload config: `swaymsg reload` (Sway) or `i3-msg reload` (i3).

### Hyprland

Add to `~/.config/hypr/hyprland.conf`:

```
windowrulev2 = float, class:^(deskmate)$
windowrulev2 = pin, class:^(deskmate)$
```

`pin` makes the window visible on all workspaces.

### KDE Plasma

1. Right-click the title bar > **More Actions** > **Configure Special Window Settings**
2. Add a new rule matching **Window class** = `deskmate`
3. Set **Desktop** to **Force** > **All Desktops**
4. Set **Keep above** to **Force** > **Yes**

Or use `kwriteconfig6`:

```bash
kwriteconfig6 --file kwinrulesrc --group 1 --key wmclass deskmate
kwriteconfig6 --file kwinrulesrc --group 1 --key desktops AllDesktops
kwriteconfig6 --file kwinrulesrc --group 1 --key desktopsrule 2
qdbus org.kde.KWin /KWin reconfigure
```

### GNOME (Mutter)

GNOME doesn't have built-in window rules. Use the [Window Calls](https://extensions.gnome.org/extension/4724/window-calls/) extension or `wmctrl`:

```bash
# After launching the app:
wmctrl -r "deskmate" -b add,sticky,above
```

To automate, add the command to a startup script or use `devilspie2`:

```lua
-- ~/.config/devilspie2/deskmate.lua
if get_application_name() == "deskmate" then
  make_always_on_top()
  stick_window()
end
```

### X11 (generic)

For any X11 window manager, `wmctrl` or `xdotool` can set sticky + always-on-top:

```bash
wmctrl -r "deskmate" -b add,sticky,above
```

## Quake Terminal (Conversation History)

DeskMate includes a quake-style dropdown terminal (toggled by Ctrl+Alt+` or via the context menu) that runs `openclaw tui` by default. Configure it in `~/.config/deskmate/config.yaml`:

```yaml
quake_terminal:
  enabled: true
  hotkey: ctrl+alt+`
  terminal_emulator: null   # null = auto-detect; or "foot", "kitty", etc.
  command: openclaw tui
  height_percent: 40
```

### Dependencies

- **Sway**: No extra dependencies (uses `swayipc` built into the binary)
- **X11**: Requires `xdotool` for hiding/showing the terminal window
  - Arch: `sudo pacman -S xdotool`
  - Debian/Ubuntu: `sudo apt install xdotool`

### Remote OpenClaw via SSH

If your OpenClaw instance runs on a remote machine, you can point the quake terminal at it over SSH. Use `ssh -t` to force PTY allocation (required by terminal multiplexers like byobu/tmux):

```yaml
quake_terminal:
  enabled: true
  hotkey: ctrl+alt+`
  command: ssh -t user@remote TERM=xterm-256color bash -li -c 'openclaw tui'
```

- `TERM=xterm-256color` ensures the remote side knows to use 256-color output. Without this, colors may be missing if the remote doesn't have the local terminal's terminfo entry (common with foot, kitty, alacritty).
- `bash -li -c '...'` runs an interactive login shell that sources your full profile (`.bash_profile`, `.bashrc`, etc.). This ensures commands installed in user-local paths (`~/.local/bin`, `~/.cargo/bin`) are in PATH.

For tmux/byobu session reattachment:

```yaml
  command: ssh -t user@remote TERM=xterm-256color bash -li -c 'byobu a -t session-name'
```

**Common pitfalls:**

- **Missing `-t` flag**: byobu/tmux requires a PTY. Without `-t`, you get `not a terminal` errors.
- **Command not found**: if you omit `bash -li -c`, SSH runs a non-interactive shell that skips your profile. `-l` sources login files (`.bash_profile`), `-i` sources `.bashrc`. You typically need both.
- Don't forget to set up your SSH tunnel for the gateway WebSocket too (e.g., `ssh -L 18789:localhost:18789 user@remote`).

### Keyboard Shortcut (Wayland)

Wayland compositors don't support application-level global hotkeys. DeskMate listens for Unix signals to toggle features, so you can bind keys in your compositor config.

| Signal | Action | Command |
|--------|--------|---------|
| `SIGUSR1` | Toggle quake terminal | `pkill -USR1 -x deskmate` |
| `SIGUSR2` | Toggle ghost visibility (show/hide) | `pkill -USR2 -x deskmate` |

**Sway / i3:**

Add to `~/.config/sway/config` (or `~/.config/i3/config`):

```
bindsym Ctrl+Alt+grave exec pkill -USR1 -x deskmate
bindsym Ctrl+Alt+h exec pkill -USR2 -x deskmate
```

(`grave` is the backtick `` ` `` key.)

**Hyprland:**

Add to `~/.config/hypr/hyprland.conf`:

```
bind = CTRL ALT, grave, exec, pkill -USR1 -x deskmate
```

**Other compositors / X11:**

Any tool that can bind a key to a shell command works. The command is always `pkill -USR1 -x deskmate`.

## Personality & Talking Style

DeskMate's personality is controlled by two files on the gateway's system prompt:

- **`SOUL.md`** — Core personality foundations (helpfulness, boundaries, continuity). Contains an include directive that loads the active skin's talking style.
- **`style.md`** (per skin) — The character's talking style, speech patterns, emotional reactions, and expression allowlist. Each skin ships its own `style.md`.

When you switch skins, swap which `style.md` the SOUL.md directive points to. Your `SOUL.md` should include something like:

```markdown
## Talking Styles

> **⚠️ REQUIRED:** Read and follow `TALKING_STYLE.md` — it contains your full
> talking style rules. Treat its contents as if they were written directly here.
> Do not respond without first loading that file.
```

See [Skin Creator Guide](docs/SKIN_CREATORS_GUIDE.md) for how to write a `style.md` for your skin.

## Development

See [CLAUDE.md](CLAUDE.md) for build instructions and architecture details.
