# WebKitGTK Transparent Window Bleed

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
- APNG frame changes — a looping APNG on a single `<img>` element (no src changes, no nudge) still bleeds between frames. The browser's internal APNG renderer does NOT trigger compositor repaints on transparent windows.
- GTK `queue_draw()` on the WebKitWebView widget via `webview.with_webview()` — does NOT trigger compositor repaint on transparent windows
- Cairo clear (`set_operator(SOURCE)` + `set_source_rgba(0,0,0,0)` + `paint()`) in a `connect_draw` handler before `queue_draw()` — clears the texture but does NOT fix bleed
- Enabling GPU compositing (`WEBKIT_DISABLE_COMPOSITING_MODE=0 WEBKIT_DISABLE_DMABUF_RENDERER=1`) — bleed persists with GPU compositing active too
- React `key` change to force DOM recreation — element destruction causes unfixable bleed

## Working Fix: Window Size Nudge

Resizing the window by 1px forces the compositor to repaint. Must wait one animation frame (`requestAnimationFrame`) between resize and restore — without the wait, the compositor doesn't process the change. Then restore original size and position. Must use `PhysicalSize`/`PhysicalPosition` (not Logical) to avoid coordinate mismatch on HiDPI Wayland. There is a slight visible budge.

See `useBubble.ts` `nudgeWindowRepaint()` and `Ghost.tsx` `runNudge()`.

**Constraint: requires floating window.** On tiling WMs (Sway), `setSize` is ignored for tiled windows. The ghost window must be floating (`for_window [app_id="..."] floating enable` in Sway config).

## Ghost Window Nudge (Ghost.tsx)

The ghost `<img>` expression change nudge cannot be simplified to a single mechanism:

- **`onLoad`** provides correct paint timing (image is loaded and composited before nudge), but does NOT fire for cached images when `src` changes on the same `<img>` element in WebKitGTK.
- **`useEffect` on `imageSrc`** catches cached image changes that `onLoad` misses, but a nudge triggered ONLY from `useEffect` (even with `img.decode()` + double rAF) fires before the compositor has actually painted — the nudge repaints stale pixels.
- **Both are needed:** `onLoad` calls `runNudge()` for fresh loads; `useEffect` with `requestAnimationFrame` wrapper calls `runNudge()` as fallback for cached images, using `lastNudgedSrc` to skip if `onLoad` already handled it.
- The `nudgeDirty` ref handles expression changes during an in-progress nudge (re-nudge after current cycle completes).

**Failed attempts:** `useEffect`-only with `setTimeout(150)`, `useEffect`-only with double rAF, `key={imageSrc}` to force DOM recreation, `win.hide()`/`win.show()` cycle.

## Idle Animation Bleed Avoidance

For APNG idle animation replay, do NOT use React `key` to force `<img>` DOM recreation — element destruction causes bleed. Instead, append a URL fragment (`#replay=N`) to the image src. The browser treats this as a new URL and re-decodes the APNG from frame 1, but the `<img>` element stays in the DOM.

## Bubble Window Event Sequencing

The bubble window lifecycle involves multiple async operations that must be carefully sequenced to avoid races:

1. **`nudgeWindowRepaint()`** (BubbleWindow) — reads `outerSize`, bumps +1px, waits, restores. Must fully complete before any content measurement, otherwise it overwrites subsequent `setSize` calls.
2. **`bubble-content-sized`** event (BubbleWindow → App) — measures visible content size. Must fire AFTER nudge completes (nudge restores the window to its pre-nudge size, and measurement reads `window.innerWidth/Height`).
3. **`resizeWindow` + `moveWindow`** (App positioning effect) — resizes to content size and repositions. Must use actual size from `resizeWindow` return value.

**Sequencing rule:** nudge → measure → emit content-sized → resize → reposition. Breaking this order causes the window to appear at wrong positions or sizes.

**Split effects rule:** The bubble popup has two separate effects in App.tsx:
- **Data emit effect** (synchronous): sends bubble data (items, theme, streaming state) to BubbleWindow via `bubble-update` event. Fires on every data change. Uses cached offsets from last positioning.
- **Positioning effect** (async): resizes and repositions the window. Only fires when `bubbleWindowSize` or `bubble.isVisible` changes. Stores computed offsets in a ref for the data effect to use.

Mixing async positioning into the data effect causes races — when multiple deps change in quick succession (e.g., streaming ends + content-sized arrives), multiple async IIFEs run concurrently and the last to finish wins, which may be a stale one.

## Why Overlays Were Rejected

Overlays (DOM within the transparent ghost window) avoid the Wayland positioning problem but require a much larger transparent window to contain the bubble, input, and ghost together. Most of that enlarged window is visually empty, yet it intercepts all clicks — the user clicks what looks like the desktop or another app, but the transparent window swallows the event. `setIgnoreCursorEvents` is all-or-nothing for the entire window, and forwarding click events to the app behind is non-trivial. This is unacceptable UX.

## Rules

- All popup UI (bubble, input, settings, skin picker) uses separate windows — never overlays in the ghost window
- Never use opacity transitions on transparent windows
- Call `window.setFocus()` after showing a window that needs keyboard input
- Separate windows are hidden by default (`visible: false`), shown/hidden via `win.show()`/`win.hide()`
- Inter-window communication uses Tauri events, not shared React state
