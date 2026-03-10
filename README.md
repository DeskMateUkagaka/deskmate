# Ukagaka

AI-powered desktop companion built with Tauri v2. A transparent character sits on your desktop, connected to an OpenClaw AI gateway for chat.

## Window Manager Configuration

The ghost window must be **floating** and **visible on all workspaces** (sticky) for proper behavior. Tiled mode breaks transparency, dismiss repaint, and positioning.

### Sway / i3

Add to your Sway or i3 config (`~/.config/sway/config` or `~/.config/i3/config`):

```
for_window [app_id="com.openclaw.ukagaka"] floating enable
for_window [app_id="com.openclaw.ukagaka"] sticky enable
```

Reload config: `swaymsg reload` (Sway) or `i3-msg reload` (i3).

### Hyprland

Add to `~/.config/hypr/hyprland.conf`:

```
windowrulev2 = float, class:^(com\.openclaw\.ukagaka)$
windowrulev2 = pin, class:^(com\.openclaw\.ukagaka)$
```

`pin` makes the window visible on all workspaces.

### KDE Plasma

1. Right-click the title bar > **More Actions** > **Configure Special Window Settings**
2. Add a new rule matching **Window class** = `com.openclaw.ukagaka`
3. Set **Desktop** to **Force** > **All Desktops**
4. Set **Keep above** to **Force** > **Yes**

Or use `kwriteconfig6`:

```bash
kwriteconfig6 --file kwinrulesrc --group 1 --key wmclass com.openclaw.ukagaka
kwriteconfig6 --file kwinrulesrc --group 1 --key desktops AllDesktops
kwriteconfig6 --file kwinrulesrc --group 1 --key desktopsrule 2
qdbus org.kde.KWin /KWin reconfigure
```

### GNOME (Mutter)

GNOME doesn't have built-in window rules. Use the [Window Calls](https://extensions.gnome.org/extension/4724/window-calls/) extension or `wmctrl`:

```bash
# After launching the app:
wmctrl -r "ukagaka" -b add,sticky,above
```

To automate, add the command to a startup script or use `devilspie2`:

```lua
-- ~/.config/devilspie2/ukagaka.lua
if get_application_name() == "ukagaka" then
  make_always_on_top()
  stick_window()
end
```

### X11 (generic)

For any X11 window manager, `wmctrl` or `xdotool` can set sticky + always-on-top:

```bash
wmctrl -r "ukagaka" -b add,sticky,above
```

## Development

See [CLAUDE.md](CLAUDE.md) for build instructions and architecture details.
