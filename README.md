# DeskMate

![DeskMate screenshot](pics/screenshot.apng)

DeskMate is an AI-powered desktop accessory in the spirit of Ukagaka.

It puts a character on your desktop, gives that character a visual identity through skins and expressions, and acts as a front end for OpenClaw so the character can talk, react, and feel present instead of living in a browser tab.

## What DeskMate Is

- Historically inspired by Ukagaka-style desktop mascots and assistants
- A desktop accessory, not just a chat window
- An OpenClaw front end with character presentation, expressions, skins, and on-desktop interaction
- Built for users who want their AI to feel like a desktop resident instead of a generic assistant panel

## Installing

Packaging and installation steps still need to be written.

For now, development and architecture notes live in `CLAUDE.md`.

## First Run

On first launch, DeskMate needs your OpenClaw gateway token. Find it in `~/.openclaw/openclaw.json` under `gateway.auth.token`, then paste it into Settings > Token (right-click the tray icon to open Settings).

## Personality And Talking Style

After installing DeskMate, set up your character's talking style through OpenClaw's prompt files.

DeskMate itself renders the character and chat UI, but the actual personality comes from the prompt content your OpenClaw bot reads.

### Recommended Setup

1. Pick the skin you want to use.
2. Take that skin's `style.md` as the basis for the character's talking style.
3. Put those rules into a file such as `TSUNDERE.md` in the place your bot reads prompt files from.
4. Add this snippet to `SOUL.md`:

```markdown
## Talking Styles

> **REQUIRED:** Read and follow `TSUNDERE.md` — it contains your full talking style rules. Treat its contents as if they were written directly here. Do not respond without first loading that file.
```

`TSUNDERE.md` can come directly from the skin's `style.md`, or you can edit it to invent your own character voice. Users are absolutely free to create their own talking style instead of using the shipped one.

After updating `SOUL.md`, send `/new` to the bot. That causes it to re-read `SOUL.md`, and the updated talking style should take effect.

## Skin Talking Styles

Each skin can define its own speech style. In this repository, the default skin's talking style lives at:

`app/skins/default/style.md`

In an installed DeskMate setup, each installed skin keeps its talking style file in DeskMate's data directory:

`<data directory>/skins/SKIN_NAME/style.md`

The exact data directory depends on your operating system.

Linux:
`~/.local/share/deskmate/skins/SKIN_NAME/style.md`

macOS:
`~/Library/Application Support/deskmate/skins/SKIN_NAME/style.md`

Windows:
`%APPDATA%\deskmate\skins\SKIN_NAME\style.md`

Examples:

- Linux default skin: `~/.local/share/deskmate/skins/default/style.md`
- macOS default skin: `~/Library/Application Support/deskmate/skins/default/style.md`
- Windows default skin: `%APPDATA%\deskmate\skins\default\style.md`

If you are making or distributing skins, treat `style.md` as the source material for that skin's voice and behavior.

## Development

See `CLAUDE.md` for development setup, architecture notes, and platform-specific details.

## Licensing

DeskMate itself is licensed under `LICENSE`.

DeskMate also uses third-party software, most notably `PySide6` / Qt for Python and Qt WebEngine. See `THIRD_PARTY_NOTICES.md` for attribution and distribution notes.
