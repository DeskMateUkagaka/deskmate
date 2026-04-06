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
format_version: 1          # 1 = static PNGs, 2 = Live2D support

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

### Live2D Skin (format_version: 2)

```yaml
type: live2d
format_version: 2
name: My Live2D Skin
author: Artist Name
version: 1.0.0

live2d:
  model: model/Character.model3.json   # Path to .model3.json relative to skin dir
  scale: 1.0                           # Model scale (default 1.0)
  anchor_x: 0.5                        # Horizontal anchor 0-1 (default 0.5)
  anchor_y: 0.5                        # Vertical anchor 0-1 (default 0.5)
  idle_motion_group: "Idle"            # Motion group for idle animations
  lip_sync: true                       # Enable mouth movement during AI streaming
  lip_sync_param: "ParamMouthOpenY"    # Model parameter for mouth opening
  expressions:
    neutral:                           # Required; list of expression/motion combos (random pick)
      - { expression: "F01" }
    happy:
      - { expression: "F02", motion_group: "Happy", motion_index: 0 }
      - { expression: "F03" }          # Multiple variants supported
    sad:
      - { expression: "F04" }
    thinking:
      - { motion_group: "Idle", motion_index: 1 }  # Motion-only (no expression file)

# No top-level `emotions:` block needed — derived from live2d.expressions keys
```

Live2D skins use the Cubism SDK rendered in QWebEngineView via pixi-live2d-display. The model gets automatic breathing, blinking, and physics. Python-side idle animations are disabled; the model's idle motion group handles idle behavior.

Expression mappings are explicit — the skin author maps DeskMate emotion names to the model's expression IDs and/or motion groups. Each emotion is a list (random variant picked at runtime, same as static skins).

### Validation Rules

- `neutral` emotion/expression is required (used as fallback)
- For static skins: all declared emotion PNG files must exist on disk
- For live2d skins: the `.model3.json` file must exist
- `format_version` must be <= app's supported version (currently 2)

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
