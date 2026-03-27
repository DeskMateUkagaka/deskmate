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

### IdleAnimationManager (`app/src/lib/idle.py`)

A `QObject` with two `QTimer` instances (single-shot):
- **`_idle_timer`**: fires after `idle_interval_seconds ± 10% jitter` to pick and start an animation
- **`_anim_timer`**: fires after `duration_ms` to clear the animation and restart the idle cycle

Signals:
- `idle_override(str)` — emitted with the animation file path; ghost displays it
- `idle_cleared()` — emitted when animation ends; ghost restores current expression

Methods:
- `start()` — begin the idle timer cycle
- `stop()` — stop all timers, clear any playing animation
- `reset()` — cancel current animation, restart timer (called on user interaction)
- `set_skin(SkinInfo)` — update available animations from skin manifest
- `set_interval(seconds)` — update the idle interval
- `set_enabled(bool)` — enable/disable the system

### Integration (`app/main.py`)

- `idle_override` signal → `ghost.set_idle_override(path)` (loads and displays the image via QWebEngineView)
- `idle_cleared` signal → `ghost.clear_idle_override()` (restores current expression)
- `_on_chat_send()` calls `idle_manager.reset()` (user interaction)
- Chat returning to idle + bubble not visible → `idle_manager.start()`
- App launch → `idle_manager.start()`

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
- Chat message sent
- Chat state transitions (sending/streaming disables idle; timer restarts when chat returns to idle and bubble dismisses)

## Backward Compatibility

- Skins without `idle_animations` work identically (empty list, no idle behavior)
- `idle_interval_seconds` defaults to 30.0 if absent from config
- Existing skins continue to work without modification
