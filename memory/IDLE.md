# Idle Animation System

The ghost supports idle animations — short clips that play when the user hasn't interacted for a while, making the character feel alive like RTS units fidgeting.

## How It Works

1. User stops interacting (no clicks, keys, drags, or chat messages)
2. After N seconds (user-configurable `idle_interval_seconds` in config.yaml, default 30, ±10% random jitter), one random idle animation plays
3. The current expression (e.g., "happy") is temporarily replaced by the animation
4. After `duration_ms`, the previous expression is restored
5. Cycle repeats indefinitely while idle

Any user interaction (click, keyboard, drag, incoming AI message) immediately cancels the animation and restarts the timer.

Idle animations do NOT play while the chat bubble is visible (user is reading a response).

## Manifest Format

Add `idle_animations` to `manifest.yaml`:

```yaml
name: My Character
author: Example
version: 1.0.0

emotions:
  neutral: neutral.png
  happy: happy.png

idle_animations:
  - file: idle-blink.apng
    duration_ms: 500
  - file: idle-yawn.apng
    duration_ms: 2000
  - file: idle-wink.png        # static PNGs work too — shown for duration_ms
    duration_ms: 1500
```

The interval between idle animations is a per-user setting in `config.yaml` (`idle_interval_seconds`, default 30.0). It is NOT in the skin manifest.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `idle_animations` | list | No | List of idle animation entries. If absent or empty, no idle behavior. |
| `idle_animations[].file` | string | Yes | Filename relative to skin directory. APNG or PNG. |
| `idle_animations[].duration_ms` | integer | Yes | How long to show the animation before restoring the expression. Must be > 0. |

## Supported Formats

- **APNG** (Animated PNG) — plays the animation frames, then restores. Recommended: set loop count to 1 in the APNG metadata so the animation doesn't loop past `duration_ms`.
- **PNG** (static) — displays the image for `duration_ms`, then restores. Useful for simple expression changes like a wink or blink without needing animation frames.

Both formats support full alpha transparency (required for the transparent ghost window).

## Creating APNG Files

From individual PNG frames:

```bash
# Install apngasm (Arch: pacman -S apngasm, Ubuntu: apt install apngasm)
apngasm idle-blink.apng frame1.png frame2.png frame3.png --delay 100 --loops 1
```

The `--loops 1` flag sets the APNG to play once (recommended). The `--delay 100` sets 100ms between frames. Total `duration_ms` in the manifest should match the sum of all frame delays (here: 3 frames × 100ms = 300ms).

## Architecture

### Frontend

- **`useIdleAnimation` hook** (`app/src/hooks/useIdleAnimation.ts`) — timer management, state machine (IDLE → ANIMATING → restore → IDLE), random selection with jitter. Takes `idleIntervalSeconds` from user settings.
- **`App.tsx`** — wires the hook, passes `idleOverrideUrl` as emotion override, passes `settings.idle_interval_seconds`, calls `resetIdleTimer()` from all interaction handlers
- **`Ghost.tsx`** — `imageKey` prop appended as URL fragment (`#replay=N`) to force APNG re-decode without DOM element destruction (which causes unfixable bleed on WebKitGTK)

### Backend (Rust)

- **`SkinManifest` / `SkinInfo`** (`app/src-tauri/src/skin/types.rs`) — `idle_animations: Vec<IdleAnimation>` with serde defaults for backward compatibility. `idle_interval_seconds` lives in user `Settings` (`config.yaml`), not in the skin manifest.
- **`SkinManager::load_skin()`** (`app/src-tauri/src/skin/loader.rs`) — validates idle animation files exist on disk, checks path traversal, enforces minimum values
- **`get_idle_animation_path`** command — resolves filename to absolute path with allowlist + canonicalization guard

### State Machine

```
        interaction
 IDLE ──────────────> IDLE (timer reset, new jitter)
  │
  │ timer fires (N seconds ± 10%)
  v
ANIMATING ──────────> IDLE (duration_ms elapsed, expression restored)
  │
  │ interaction
  v
 IDLE (animation cancelled, expression restored, timer reset)
```

### Interaction Events That Reset Timer

- Mouse click on ghost (left or right)
- Keyboard shortcuts (Enter, Escape, etc.)
- Dragging the ghost
- Chat state transitions (sending/streaming disables idle via `enabled` flag; timer restarts when chat returns to idle and bubble dismisses)

### APNG Replay Mechanism

APNG in `<img>` tags loops by default and doesn't restart when the same URL is re-assigned. To force replay from frame 1, the hook increments `idlePlayCount` each time an animation starts. App.tsx passes this as `imageKey` to Ghost.tsx, which appends it as a URL fragment (`#replay=N`) to the image src. The browser treats this as a new URL and re-decodes the APNG from frame 1, without destroying the DOM element.

**Why not React `key`?** Using `key={imageKey}` would force React to destroy and recreate the `<img>` element. On WebKitGTK transparent windows, element destruction causes bleed artifacts (old pixels persist) that the subsequent nudge cannot always clear reliably. The URL fragment approach keeps the same DOM element alive, avoiding destruction bleed entirely.

### Nudge Concurrency Guard

Ghost.tsx runs a "nudge" cycle on each `<img onLoad>` to clear WebKitGTK compositor bleed artifacts (resize +1px → wait → restore). Rapid image source changes (APNG → static on interaction interrupt) can trigger concurrent nudges. A `nudgeInProgress` ref serializes these operations — if a new `onLoad` fires while a nudge is in progress, the second nudge is skipped.

## Backward Compatibility

- Skins without `idle_animations` work identically to before (serde defaults to empty Vec)
- `idle_interval_seconds` defaults to 30.0 if absent
- No `format_version` bump required — older app versions silently ignore unknown YAML fields via serde defaults
- Existing `format_version: 1` skins continue to work without modification

## Security

- Idle animation filenames must be declared in the manifest (allowlist prevents arbitrary frontend requests)
- Path canonicalization (`canonicalize()` + `starts_with(base_path)`) prevents path traversal both at load time and at request time
- Community skins with `file: "../../etc/passwd"` in the manifest are rejected during skin loading
