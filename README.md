# DeskMate

![DeskMate screenshot](pics/screenshot.apng)

Remember Ukagaka? Those little desktop characters that just... lived on your screen? DeskMate is that idea brought back to life with AI.

Your character sits right on your desktop — not trapped in a browser tab, not hiding behind a chat window. They have expressions, skins, and a personality. They talk to you. They react. They're just *there*, hanging out while you do your thing.

DeskMate connects to [OpenClaw](https://openclaw.ai) as the AI backend, so the character actually has a brain behind the cute face.

## Why?

- You miss desktop mascots and want that vibe back, but smarter
- You'd rather talk to a character on your desktop than yet another chat UI
- You want your AI companion to have a face, a mood, and a home on your screen
- You like customizing things — skins, expressions, personalities, the works

## Installing

Proper packaging is still in the works. For now, check `CLAUDE.md` for how to run it from source.

## Getting Started

When you first launch DeskMate, it'll need your OpenClaw gateway token. Grab it from `~/.openclaw/openclaw.json` (look for `gateway.auth.token`), then right-click the tray icon, open Settings, and paste it in.

## Give Your Character a Voice

DeskMate handles the visuals — the character, expressions, chat bubbles — but the personality? That comes from your OpenClaw prompt setup. Here's how to get that going:

1. Pick a skin you like.
2. Grab that skin's `style.md` — it's a starting point for how the character talks.
3. Copy it (or write your own!) into something like `TSUNDERE.md` where your bot reads prompt files.
4. Tell your bot to use it by adding this to `SOUL.md`:

```markdown
## Talking Styles

> **REQUIRED:** Read and follow `TSUNDERE.md` — it contains your full talking style rules. Treat its contents as if they were written directly here. Do not respond without first loading that file.
```

You can use the skin's style as-is, tweak it, or throw it out and write something totally different. It's your character — make them sound however you want.

Once you've updated `SOUL.md`, send `/new` to the bot so it picks up the changes.

## Skin Styles

Every skin can ship with its own `style.md` that defines how the character talks. In the repo, the default one lives at:

`app/skins/default/style.md`

Once installed, skins keep their style files in DeskMate's data directory:

| Platform | Path |
|----------|------|
| Linux | `~/.local/share/deskmate/skins/SKIN_NAME/style.md` |
| macOS | `~/Library/Application Support/deskmate/skins/SKIN_NAME/style.md` |
| Windows | `%LOCALAPPDATA%\deskmate\deskmate\skins\SKIN_NAME\style.md` |

If you're making or sharing skins, `style.md` is where you define the character's voice and vibe.

## Keyboard Shortcuts

### Windows

| Shortcut | Action |
|----------|--------|
| `Win+F12` | Toggle ghost visibility — global, works from any app |
| `Ctrl+`` | Toggle chat history terminal — global, works from any app |
| `Win+`` | Toggle chat history terminal visibility (Windows Terminal's built-in quake mode — works once the terminal is open) |
| `Enter` | Open chat input (when ghost is focused) |
| `Ctrl+Q` | Quit |

On the first <code>Ctrl+`</code>, DeskMate spawns Windows Terminal in quake mode running the configured command (default: `openclaw tui`). After that, both <code>Ctrl+`</code> and <code>Win+`</code> toggle its visibility.

### Linux / macOS

| Shortcut | Action |
|----------|--------|
| <code>Ctrl+`</code> | Toggle chat history terminal (macOS: physical Ctrl, not Cmd) |
| Bare <code>`</code> | Toggle chat history terminal (when ghost is focused) |
| `Enter` | Open chat input (when ghost is focused) |
| `Ctrl+Q` | Quit |

You can also use signals to toggle from any context (e.g. from a window manager keybinding):

```
pkill -USR1 -x deskmate   # toggle chat history terminal
pkill -USR2 -x deskmate   # toggle ghost visibility
```

On Linux, the chat history uses an embedded terminal (xterm.js + pty). SIGUSR signals work on both Linux and macOS.

## Development

See `CLAUDE.md` and `DEV.md` for dev setup, architecture, and platform quirks.

## License

DeskMate is licensed under `LICENSE`.

Third-party notices (PySide6/Qt, Qt WebEngine, etc.) are in `THIRD_PARTY_NOTICES.md`.
