# DEV.md — Developer Guide

## Prerequisites

- **Python 3.13+**
- **PySide6** (Qt6 + QtWebEngine)
- **uv** (recommended) or pip

## Getting Started

```bash
cd app
uv pip install -r requirements.txt
python3 main.py
```

First run creates `~/.config/deskmate/` with default settings and a generated Ed25519 device identity.

**Sway users** need this in their config:
```
for_window [app_id="deskmate"] floating enable
```

## Debug Cheat Codes

Type these into the chat input. They bypass the gateway entirely — no connection needed.

- **`ack`** — Show a hardcoded "ACK" bubble immediately. Tests bubble display without hitting the gateway.
- **`emo`** — Switch to a random non-neutral expression. Tests ghost expression rendering.
- **`md`** — Stream a sample Markdown document (headers, bold, code blocks, tables, lists, blockquote, link) into the bubble. Simulates real gateway streaming at ~10 chars/30ms. Tests bubble markdown rendering and streaming cursor animation.

## Rendering Quality: QPainter vs QWebEngineView (Chromium)

The ghost window uses QWebEngineView (Chromium `<img>` tag) instead of QPainter for image rendering. This was a deliberate choice after observing significantly worse anti-aliasing with vanilla Qt. The difference comes from three layers:

### 1. Scaling Algorithm

- **QPainter `SmoothTransformation`**: Bilinear interpolation (2x2 pixel sample). Fast but soft, especially on large downscales like 3133px → 540px.
- **Chrome `<img>`**: Lanczos-3 resampling (6x6 sinc-based kernel). Much better edge preservation.

### 2. Compositing Pipeline

- **QPainter**: CPU-based software rasterizer. Scales the image, then blits it onto the window surface with basic alpha blending. The transparent window compositing is also done in software.
- **Chrome (Skia)**: GPU-accelerated compositing with **premultiplied alpha** throughout the entire pipeline. Image decode, scale, and composite all happen on the GPU with proper filtering at every step.

### 3. Why Pillow Lanczos Didn't Help

We tried replacing Qt's scaler with Pillow's Lanczos (the same algorithm browsers use). Quality didn't improve because the bottleneck was **not the scaling step** — it was QPainter's compositing. When QPainter draws the scaled QPixmap onto the transparent window, it uses bilinear filtering *again* for the final blit. Even a perfectly scaled image gets degraded at the compositing stage.

Chrome avoids this entirely because Skia renders the `<img>` directly to a GPU texture that the Wayland compositor receives as-is — no extra software compositing step.

**Conclusion**: For any transparent window that needs high-quality image rendering on Qt, use QWebEngineView with an `<img>` tag instead of QPainter. The tradeoff is higher memory usage (each QWebEngineView is a Chromium instance) but the visual quality matches browser rendering exactly — because it *is* browser rendering.

### Mouse Event Interception on QWebEngineView

QWebEngineView creates internal child widgets (`RenderWidgetHostViewQtDelegateWidget`) that swallow all mouse events. To handle drag and click on a QWebEngineView-based window:

1. Install an `eventFilter` recursively on all child widgets after `loadFinished`
2. Also handle `ChildAdded` events to catch widgets created dynamically
3. Use `windowHandle().startSystemMove()` for drag — this delegates to the Wayland compositor natively (QWidget.move() is ignored on Wayland)
4. Distinguish click vs drag by checking manhattan distance between press and release positions

See `ghost.py` `eventFilter()` and `_install_filters_recursive()`.

## Fractional Scaling (Wayland)

Sway with fractional scale (e.g., 1.333x) causes blurry rendering in ALL Qt/GTK apps. The compositor sends integer scale 2 to apps via `wl_output.scale`, then downscales the 2x buffer to 1.33x. This double-scaling causes blur and is not fixable from the app side. Integer scales (1x, 2x) render sharply.

Relevant issues:
- [sway#8131](https://github.com/swaywm/sway/issues/8131) — Blurry scaling for native Wayland apps
- [sway#7463](https://github.com/swaywm/sway/issues/7463) — Rounding issues with wp-fractional-scaling

## Key Files

| Area | File |
|------|------|
| App entry / orchestrator | `app/main.py` |
| Ghost window (QWebEngineView) | `app/src/windows/ghost.py` |
| Chat bubble (QWebEngineView) | `app/src/windows/bubble.py` |
| Chat input | `app/src/windows/chat_input.py` |
| Settings window | `app/src/windows/settings.py` |
| Skin picker | `app/src/windows/skin_picker.py` |
| Gateway WebSocket client | `app/src/gateway/client.py` |
| Ed25519 device identity | `app/src/gateway/device_identity.py` |
| Protocol types | `app/src/gateway/types.py` |
| Chat session | `app/src/gateway/chat.py` |
| Settings persistence (YAML) | `app/src/lib/settings.py` |
| Skin loader | `app/src/lib/skin.py` |
| Emotion/button tag parsing | `app/src/lib/parse.py` |
| Idle animation | `app/src/lib/idle.py` |
| Quake terminal | `app/src/lib/quake_terminal.py` |
| Slash command autocomplete | `app/src/lib/commands.py` |

## Legacy Tauri App

The original Tauri v2 codebase is preserved in `app-tauri/` for reference. See `memory/BLEED.md` for documentation of the WebKitGTK transparency bleed bug that drove the migration to PySide6.
