# Skin System & Community Distribution

## Skin Format

Each skin is a folder containing:

```
my-skin/
  manifest.yaml     # Required: metadata + emotion mappings
  neutral.png       # Required: fallback emotion
  happy.png         # Optional emotion PNGs
  sad.png
  preview.png       # Used in skin picker (recommended)
  ...
```

### manifest.yaml

```yaml
name: My Skin
author: Artist Name
version: 1.0.0
format_version: 1          # 1 = static PNGs (current), 2+ = future (animated, etc.)

emotions:
  neutral:                   # Required; list of variant PNGs (random pick on each change)
    - neutral.png
  happy:
    - happy.png
    - happy2.png             # Multiple variants supported
  sad:
    - sad.png
  thinking:
    - thinking.png
  connecting:                # Shown during connection attempts; falls back to neutral
    - thinking.png
  # Any number of custom emotions

# Optional: positioning & theming
bubble_placement:
  x: -300                  # Offset from ghost image center (px)
  y: -800
  origin: bottom-right     # center | top-left | top-right | bottom-left | bottom-right

input_placement:
  x: 0
  y: 0

bubble:
  background_color: "#ffffff"
  border_color: "#d0d0d0"
  border_width: 1px
  border_radius: 12px
  text_color: "#1a1a1a"
  accent_color: "#3060c0"
  code_background: "#f5f5f5"
  code_text_color: "#333333"
  font_size: 13px
  max_bubble_width: 640
  max_bubble_height: 540

idle_animations:
  - file: idle-blink.apng
    duration_ms: 500
  - file: idle-yawn.apng
    duration_ms: 2000
```

### Validation Rules

- `neutral` emotion is required (used as fallback)
- All declared emotion PNG files must exist on disk
- `format_version` must be <= app's supported version (currently 1)

## Skin Directories

| Location | Purpose | Source tag |
|----------|---------|-----------|
| `app/skins/` | Ships with the app (bundled) | `"bundled"` |
| `~/.config/deskmate/skins/` (planned) | User-downloaded community skins | `"community"` |

`SkinLoader` scans the skins directory on startup and on `list_skins()`.

## Community Distribution — Pling/OCS

Skins are shared via [Pling](https://www.pling.com) (OpenDesktop), the same platform that powers KDE's "Get New Stuff" buttons. Creators upload via the Pling web UI; users browse and install from within DeskMate.

### Tag Convention for Creators

When uploading a skin to Pling, tag it with:

- `deskmate` — **required**, identifies it as a DeskMate skin
- `deskmate-v1` — **required**, skin format version (static PNGs)
- Additional tags for discoverability: `anime`, `cute`, `dark`, `pixel-art`, etc.

### ZIP Structure

Skin ZIPs uploaded to Pling can have either structure:

```
# Option A: files at root
my-skin.zip
  manifest.yaml
  neutral.png
  happy.png

# Option B: single subfolder
my-skin.zip
  my-skin/
    manifest.yaml
    neutral.png
    happy.png
```

## Implementation

### Python Backend (`app/src/lib/skin.py`)

- `SkinLoader` — scan, load, validate skins
- `SkinInfo` dataclass — metadata, emotions list, placements, theme, idle animations
- `UiPlacement`, `BubbleTheme`, `IdleAnimation` — supporting dataclasses
- `get_emotion_images(skin, emotion)` — returns file paths, falls back to neutral
- `get_preview_image(skin_id)` — returns path to `preview.png` or None

### Skin Picker UI (`app/src/windows/skin_picker.py`)

- `SkinPickerWindow` — grid of skin cards with preview image, name, author
- Blue highlight border on currently active skin
- Click selects and emits `skin_selected(skin_id)` signal

### Orchestration (`app/main.py`)

- `_on_skin_selected(skin_id)` — loads new skin, updates ghost, saves to settings
- `_show_skin_picker()` — populates grid with available skins, positions near ghost
- Tray menu "Change Skin" opens the picker
