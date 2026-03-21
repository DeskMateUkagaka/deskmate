# Skin System & Community Distribution

## Skin Format

Each skin is a folder containing:

```
my-skin/
  manifest.yaml     # Required: metadata + emotion mappings
  neutral.png       # Required: fallback emotion
  happy.png         # Optional emotion PNGs
  sad.png
  ...
```

### manifest.yaml

```yaml
name: My Skin
author: Artist Name
version: 1.0.0
format_version: 1          # 1 = static PNGs (current), 2+ = future (animated, etc.)

emotions:
  neutral: neutral.png     # Required
  happy: happy.png
  sad: sad.png
  thinking: thinking.png
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

input:
  max_width: 640
  max_height: 480
```

### Validation Rules

- `neutral` emotion is required (used as fallback)
- All declared emotion PNG files must exist on disk
- `format_version` must be <= app's `SUPPORTED_FORMAT_VERSION` (currently 1)

## Skin Directories

| Location | Purpose | Source tag |
|----------|---------|-----------|
| `app/skins/` (dev) / bundled resources (prod) | Ships with the app | `"bundled"` |
| `$APP_DATA_DIR/skins/` | User-downloaded community skins | `"community"` |

`SkinManager` scans both directories on startup and after `reload_skins()`.

## Community Distribution — Pling/OCS

Skins are shared via [Pling](https://www.pling.com) (OpenDesktop), the same platform that powers KDE's "Get New Stuff" buttons. Creators upload via the Pling web UI; users browse and install from within DeskMate.

### API

- **Base URL:** `https://api.pling.com/ocs/v1/`
- **Auth:** None required for reads
- **Browse:** `GET /content/data?format=json&categories=464&tags=deskmate,deskmate-v1&sortmode=new&pagesize=20`
- **Download:** `downloadlink1` field in response (JWT-signed, time-limited URL)
- **Sort modes:** `new` | `down` (most downloaded) | `high` (highest rated) | `alpha`
- **Tag filtering:** `tags=` is a Pling-specific extension (not in OCS 1.7 spec). Exact token match, comma-separated = AND logic.

### Tag Convention for Creators

When uploading a skin to Pling, tag it with:

- `deskmate` — **required**, identifies it as a DeskMate skin
- `deskmate-v1` — **required**, skin format version (static PNGs)
- Additional tags for discoverability: `anime`, `cute`, `dark`, `pixel-art`, etc.

Future format versions will use `deskmate-v2`, `deskmate-v3`, etc.

### Category

Currently using category **464** (Various Stuff). A dedicated DeskMate category should be requested from `contact@opendesktop.org`.

### ZIP Structure

Skin ZIPs uploaded to Pling can have either structure — the installer handles both:

```
# Option A: files at root
my-skin.zip
  manifest.yaml
  neutral.png
  happy.png
  ...

# Option B: single subfolder
my-skin.zip
  my-skin/
    manifest.yaml
    neutral.png
    happy.png
    ...
```

The installer skips `__MACOSX/` and `.DS_Store` files.

## In-App "Get Skins" Window

- **Window:** 1280x720, separate Tauri window (`label: "get-skins"`)
- **Accessible from:** tray menu, right-click context menu
- **Features:** search, sort (newest/downloads/rating), thumbnail grid, install with progress bar, "Installed" badge
- **Post-install:** emits `skin-installed` Tauri event → skin picker auto-refreshes

## Key Files

### Rust Backend
- `app/src-tauri/src/skin/loader.rs` — `SkinManager`: scan, load, validate, install, switch
- `app/src-tauri/src/skin/types.rs` — `SkinManifest`, `SkinInfo`, `BubbleTheme`, `UiPlacement`
- `app/src-tauri/src/ocs/client.rs` — OCS API HTTP client (browse + streaming download)
- `app/src-tauri/src/ocs/types.rs` — `OcsResponse`, `OcsContentItem`, `OcsBrowseParams`
- `app/src-tauri/src/commands/skin.rs` — Tauri commands: list, switch, get emotion image, reload
- `app/src-tauri/src/commands/ocs.rs` — Tauri commands: browse, download+install, get installed IDs

### React Frontend
- `app/src/hooks/useSkin.ts` — skin state, emotion preloading, auto-reload on `skin-installed`
- `app/src/hooks/useOcsSkins.ts` — OCS gallery state: search, sort, pagination, download progress
- `app/src/windows/GetSkinsWindow.tsx` — Get Skins gallery UI
- `app/src/windows/SkinPickerWindow.tsx` — local skin picker, auto-refreshes on `skin-installed`
- `app/src/types/index.ts` — `SkinInfo`, `OcsContentItem`, `OcsBrowseParams`, `SkinDownloadProgress`

### Config
- `app/src-tauri/tauri.conf.json` — window def for `get-skins`, CSP allows `images.pling.com`
- `app/src-tauri/capabilities/default.json` — `get-skins` in windows array

## Tauri Events

| Event | Direction | Payload | Purpose |
|-------|-----------|---------|---------|
| `skin-selected` | SkinPickerWindow → App | `{ id: string }` | User selected a skin |
| `skin-installed` | GetSkinsWindow → App/SkinPicker | `{ id: string }` | New skin downloaded from Pling |
| `skin-download-progress` | Rust → GetSkinsWindow | `{ downloaded, total }` | Streaming download progress |
