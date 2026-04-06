# Live2D Integration

## Architecture

Live2D models render inside GhostWindow's QWebEngineView via a separate HTML page (`GHOST_HTML_LIVE2D` built by `_live2d_html()`). The page loads PixiJS + Live2D Cubism Core + pixi-live2d-display, which handles model rendering, auto-blink, auto-breathe, physics, and idle motion scheduling.

Python controls the model via `runJavaScript()` calls to a JS API:
- `loadModel(url, scale, anchorX, anchorY, lipSyncParam)` — load a .model3.json
- `setExpression(id)` — trigger a Live2D expression (.exp3.json)
- `triggerMotion(group, index)` — play a motion from a motion group
- `startLipSync()` / `stopLipSync()` — JS-side mouth oscillation loop
- `destroy()` — clean up model and WebGL resources

JS notifies Python via QWebChannel bridge callbacks:
- `bridge.onModelLoaded()` — model ready for commands
- `bridge.onModelError(msg)` — load failure

## JS Libraries (Vendored)

All in `app/lib/live2d/`:

| File | Version | License | Purpose |
|------|---------|---------|---------|
| `pixi.min.js` | 7.3.3 | MIT | WebGL rendering engine |
| `live2dcubismcore.min.js` | 4.x | Live2D Proprietary (free <$1K) | Cubism model runtime (WASM-backed) |
| `cubism4.min.js` | 0.4.0 | MIT | Cubism 4 integration for pixi-live2d-display |
| `pixi-live2d-display.min.js` | 0.4.0 | MIT | High-level Live2D model API (auto-idle, blink, expressions) |

**Why vendored:** The app is PySide6 desktop, not a web/node project. QWebEngineView loads local HTML via `file://` URLs. No npm, no bundler.

**PixiJS v7 lock:** pixi-live2d-display 0.4.x requires PixiJS v7. If pixi-live2d-display adds v8 support, we can upgrade.

## Skin Type Routing

The `type` field in `manifest.yaml` gates all branching:

- `GhostWindow.set_skin()` loads different HTML pages per type
- `GhostWindow.set_expression()` routes to image swap (static) or JS API call (live2d)
- `IdleAnimationManager.set_skin()` disables Python idle timer for live2d (JS runtime owns idle)
- `DeskMate._on_skin_selected()` skips `_load_emotions_map()` for live2d skins

Cross-type skin switches (static→live2d or vice versa) reload the HTML page. Same-type switches reuse the page (destroy + loadModel for live2d, image swap for static).

## Expression Queue

Live2D model loading is async (HTML page load + model fetch). If `set_expression()` is called before the model is ready (e.g., `_begin_streaming()` sets "thinking" immediately), the expression is stored in `_pending_expression` with keep-last semantics. When `onModelLoaded` fires, the pending expression is applied.

## Lip Sync

Text-driven, not audio-based. Python sends `startLipSync()` on first streaming delta and `stopLipSync()` when streaming ends (2 IPC calls total). The JS side runs a `requestAnimationFrame` loop that oscillates the mouth parameter with random variation for natural movement.

The parameter name (e.g., `ParamMouthOpenY`) is configurable per model via `lip_sync_param` in the manifest.

## Creating a Live2D Skin

1. Get a Live2D model (.model3.json + .moc3 + textures + physics + motions)
   - Buy from [nizima](https://nizima.com) or [Booth](https://booth.pm)
   - Commission an artist
   - Use sample models from the [Cubism SDK](https://www.live2d.com/en/sdk/download/web/)

2. Create the skin directory:
   ```
   my-live2d-skin/
     manifest.yaml
     preview.png              # Screenshot for skin picker
     model/
       Character.model3.json
       Character.moc3
       textures/
       motions/
       expressions/           # Optional .exp3.json files
   ```

3. Write `manifest.yaml` — map DeskMate emotions to model expressions/motions.
   Check the model's `.model3.json` for available expression names and motion groups.

4. Test by placing the skin folder in `~/.local/share/deskmate/skins/` and switching via the skin picker.

## Known Limitations

- **No face tracking** — expressions driven by AI emotion tags only
- **Fractional scaling on Sway** — blurry rendering at non-integer scales (compositor limitation)
- **Expression names vary per model** — skin author must manually map them
- **Live2D Cubism Editor is Windows/Mac only** — model authoring not available on Linux natively
- **Three-type threshold** — if a third rendering backend is ever added, GhostWindow should be split into separate classes per type
