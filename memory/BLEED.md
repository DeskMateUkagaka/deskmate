# WebKitGTK Transparent Window Bleed (Historical)

> **This document is historical.** The PySide6 version of DeskMate uses QWebEngineView (Chromium), which does NOT have this bug. This file is preserved as a reference for why the framework migration from Tauri to PySide6 was necessary.

WebKitGTK has a compositor bug where transparent windows leave ghost artifacts ("bleed") when DOM elements are removed or hidden. The upstream bug ([tauri#12800](https://github.com/tauri-apps/tauri/issues/12800)) was reportedly fixed in WebKitGTK 2.48.0, but bleed still occurs on WebKitGTK 2.50.5. This affects both X11 (i3) and Wayland (Sway) — it is a WebKitGTK issue, not compositor-specific.

## What Works and What Doesn't

**Things that DO trigger repaints:**
- Text content changes during streaming (chat bubble text updates fine)
- **Window size nudge** (`nudgeWindowRepaint()`) — the only known working fix

**Things that do NOT clear bleed:**
- DOM element removal (`return null`) — old pixels persist
- CSS property changes (opacity, background, transform)
- `visibility: hidden` + `width/height: 0` + `overflow: hidden` (keeping element in DOM)
- Rendering a semi-transparent element over the bleed area
- Rendering transparent text (`color: transparent`) with changing content — only *visible* text triggers repaints
- `document.body.style.display` toggling
- Opacity transitions — cause worse bleed (window becomes fully opaque)
- New elements rendered over the bleed area
- `canvas.drawImage()` — rendering via hidden `<img>` + canvas mirror produces the same bleed as direct `<img>` usage
- APNG frame changes — a looping APNG on a single `<img>` element (no src changes, no nudge) still bleeds between frames
- GTK `queue_draw()` on the WebKitWebView widget — does NOT trigger compositor repaint on transparent windows
- Cairo clear in a `connect_draw` handler — clears the texture but does NOT fix bleed
- Enabling GPU compositing — bleed persists with GPU compositing active too
- React `key` change to force DOM recreation — element destruction causes unfixable bleed

## Resolution

The app was migrated from Tauri v2 (WebKitGTK) to PySide6 (QWebEngineView/Chromium) in March 2026. QWebEngineView does not have this bleed bug. All nudge workarounds, event sequencing hacks, and bleed-related code were removed.

See the old Tauri codebase in `app-tauri/` for the original workaround implementations.
