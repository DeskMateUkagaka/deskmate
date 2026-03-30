# Sway/wlroots Crash on Window Creation

> **Status: Upstream bug.** No app-side fix possible. Monitor wlroots releases for a patch.

## Summary

Sway crashes with SIGABRT when new windows appear while DeskMate is running. Observed when opening the quake terminal (kitty spawn) and the skin picker. The crash is an assertion failure inside wlroots' scene graph, not caused by anything DeskMate does.

## Environment

- **sway** 1.11 (`--unsupported-gpu`)
- **wlroots** 0.19.3 (Arch: `wlroots0.19 0.19.3-1`)
- **Arch Linux**, kernel 6.19.10

## Backtrace

Both observed crashes (2026-03-30) have identical backtraces:

```
#0  libc.so.6    — __pthread_kill_implementation
#1  libc.so.6    — raise
#2  libc.so.6    — abort
#3  libc.so.6    — __assert_fail
#4  libwlroots-0.19.so+0x2550d
...
#11 libwlroots-0.19.so — wlr_scene_subsurface_tree_set_clip
#12 sway+0x6043a
#13 sway+0x22907  (event dispatch)
#14 libwayland-server — wl_event_loop_dispatch
#15 libwayland-server — wl_display_run
```

## Analysis

- The crash occurs inside `wlr_scene_subsurface_tree_set_clip` — wlroots hits an assertion when updating the scene graph's subsurface clipping.
- DeskMate's windows use `FramelessWindowHint | WindowStaysOnTopHint | Tool | WA_TranslucentBackground` — standard Wayland surfaces, nothing exotic.
- The crash happens when the compositor processes a newly mapped window (kitty, skin picker QWidget), before any swaymsg IPC commands are sent.
- The `--unsupported-gpu` flag may contribute by altering the rendering path.

## Workarounds

- **Upgrade wlroots** if a newer version is available (`pacman -Syu`).
- Check upstream: `gitlab.freedesktop.org/wlroots/wlroots` for related issues.
- Removing `--unsupported-gpu` (if GPU supports sway natively) may avoid the code path.
