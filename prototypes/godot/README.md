# DeskMate Godot 4 Prototype

A transparent desktop companion prototype built in Godot 4. No external assets — everything is generated procedurally.

## Install Godot

```bash
sudo pacman -S godot
```

## Run

### From the command line (headless launch):

```bash
godot --path /home/jdj/work/ukagaka/prototypes/godot/
```

### Wayland (native, recommended on Sway/Hyprland):

```bash
godot --display-driver wayland --path /home/jdj/work/ukagaka/prototypes/godot/
```

Without `--display-driver wayland`, Godot defaults to X11/XWayland.

### From the Godot editor:

1. Open Godot
2. Import project → select `/home/jdj/work/ukagaka/prototypes/godot/`
3. Press F5 or click Run

## Keyboard Shortcuts

| Key       | Action                                                       |
|-----------|--------------------------------------------------------------|
| `Space`   | Switch expression (blue circle ↔ red circle)                 |
| `B`       | Toggle chat bubble visibility                                |
| `F`       | Fade bubble in/out (0.5s tween on `modulate.a`)             |
| `T`       | Toggle click-through mode (everywhere vs. circle area only)  |
| `H`       | Print help to stdout                                         |
| `Q` / `Esc` | Quit                                                       |

All actions print timestamped messages to stdout for tracing.

## What to Test

### Bleed artifacts on expression switch
Press `Space` rapidly to toggle between blue and red circles. On WebKitGTK (Tauri) this causes ghosting. Check whether Godot's renderer leaves stale pixels on the transparent background after switching. Expected: clean repaint with no residual pixels from the previous circle.

### Fade animation smoothness
Press `F` to fade the bubble in/out. The tween animates `modulate.a` over 0.5 seconds. Check for:
- Smooth alpha gradient with no stepping
- No compositor artifacts during the fade
- Clean disappearance at `a = 0` (no ghost outline remaining)

### Click-through behavior
Default state: full click-through (`T` mode = enabled). Clicks pass through the window entirely — you can click apps behind the companion.

Press `T` to disable click-through: only the circle area blocks clicks; everything outside the 100px-radius circle passes through.

Press `T` again to re-enable full passthrough.

Verify by clicking on a terminal or browser window positioned behind the companion.

### Transparent background
The window background should be fully transparent — you should see the desktop/wallpaper through the empty areas around the circle.

## Project Structure

```
prototypes/godot/
├── project.godot   # Godot project config (transparency, borderless, always-on-top)
├── main.tscn       # Scene: Node2D root + Sprite2D character + PanelContainer bubble
├── main.gd         # All logic: texture generation, input handling, animations
└── README.md       # This file
```

## Notes

- Window is 400×400, always-on-top, borderless, transparent.
- The circle character is 200×200px, centered at (200, 200).
- The chat bubble is a `PanelContainer` with a `StyleBoxFlat` (white, 85% opacity, rounded corners).
- `DisplayServer.window_set_mouse_passthrough()` controls click-through. An empty `PackedVector2Array` means the entire window passes clicks through. A polygon array means only the region inside the polygon blocks clicks.
- Wayland note: `always_on_top` may be ignored by tiling compositors (Sway, Hyprland) unless the window is floating. Add a window rule: `for_window [app_id="Godot*"] floating enable` in Sway config.
