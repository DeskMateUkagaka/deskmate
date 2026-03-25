# PyQt6 Transparent Desktop Companion Prototype

A minimal prototype testing PyQt6 capabilities for a transparent desktop companion on Linux (X11 / Wayland).

## How to Run

```bash
/usr/bin/python3 main.py
```

PyQt6 must be installed on the **system** Python (not a venv). On Arch:

```bash
sudo pacman -S python-pyqt6
```

## Keyboard Shortcuts

| Key     | Action                                                                 |
|---------|------------------------------------------------------------------------|
| `Space` | Switch expression: blue circle ↔ red circle                           |
| `B`     | Toggle chat bubble (instant show/hide)                                 |
| `F`     | Fade-in / fade-out animation on the bubble (300 ms)                   |
| `T`     | Toggle click-through mode (`WindowTransparentForInput` on/off)         |
| `Q`     | Quit                                                                   |

## What to Test

### 1. Bleed Artifacts on Expression Switch (`Space`)

Press `Space` rapidly to switch between blue and red circles. Watch the screen for:
- Ghost pixels from the previous circle colour that don't get cleared
- The prototype uses `CompositionMode_Clear` before each redraw to explicitly erase the background
- Two stdout log lines fire per switch: one at switch time, one 16 ms later after a forced repaint

**Expected on X11 (i3/Sway-XWayland):** usually clean if compositing is on. May show brief ghost if compositor is off.
**Expected on Wayland native:** WebKitGTK/Qt compositor interaction differs — observe whether old pixels persist.

### 2. Animation Smoothness (`F`)

Press `F` with bubble hidden → fades in. Press `F` again → fades out. Check:
- Is the 300 ms fade smooth or janky?
- Does the bubble disappear completely after fade-out (no residual translucent rectangle)?

### 3. Click-Through Behaviour (`T`)

With click-through **disabled** (default, interactive mode):
- Clicking on the window should focus it and keyboard shortcuts should work.

With click-through **enabled**:
- Mouse clicks should pass through the window to whatever is behind it.
- Keyboard shortcuts will stop working (input is fully forwarded).
- Press `T` again from another terminal / another mechanism to re-enable interactive mode.

**Known Wayland limitation:** `Qt.WindowType.WindowTransparentForInput` may be silently ignored on some Wayland compositors (Sway, GNOME). The flag works reliably on X11. On Wayland, per-region input masks require compositor-specific protocols (e.g., `wl_surface.set_input_region`) that Qt does not expose at this level. The Tauri/WebKitGTK stack has the same limitation.

### 4. Always-on-Top

Verify the companion window stays above other windows. Uses `Qt.WindowType.WindowStaysOnTopHint`. On Sway this requires the window to be floating (`for_window [app_id="..."] floating enable`).

### 5. Taskbar Skipping

The `Qt.WindowType.Tool` flag suppresses the window from appearing in taskbars and window switchers on most desktop environments.

## Known Wayland Limitations

| Feature | X11 | Wayland |
|---|---|---|
| Programmatic window positioning | Works (`setPos`) | Compositor-controlled; may be ignored |
| Click-through (`WindowTransparentForInput`) | Works | Often ignored; needs `wl_surface.set_input_region` |
| Opacity / fade animation | Works (GPU composited) | May be no-op if compositor ignores `setWindowOpacity`; `QPropertyAnimation` on a child widget's custom paint property works as a workaround |
| Always-on-top | Works | Compositor-dependent; Sway honours it for floating windows |
| Bleed / ghost pixels after clear | Rare | More likely; WebKitGTK bug also present in Qt on some drivers |

## Architecture Notes

- Single-file, no external deps beyond PyQt6.
- `BubbleWidget` is a child `QWidget` with a custom `bubbleOpacity` Qt property, allowing `QPropertyAnimation` to drive the fade without relying on `setWindowOpacity` (which affects the whole window).
- `CompositionMode_Clear` is used in `paintEvent` to explicitly erase the background before redrawing, which is the correct way to maintain transparency on each frame rather than relying on the compositor to do it.
