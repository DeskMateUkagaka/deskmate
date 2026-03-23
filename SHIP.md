# DeskMate v1 Ship Plan

## Target Audience

Launch for **Linux desktop customizers** first (r/unixporn, Sway/Hyprland/i3 users). They build from source, edit WM configs willingly, and generate screenshots that pull in the broader audience. AI companion fans and Ukagaka nostalgics come second.

## Release Day

**Wednesday.** Peak HN + Reddit tech engagement is Tue-Thu. Wednesday gives Mon+Tue as buffer; front-page discussion carries through Thursday.

## The One Critical Thing

**Real character art.** This is a visual product. Screenshots are the growth engine. One beautiful default skin with 7 expressive poses + idle animations outweighs any 5 technical features. Nobody shares a screenshot of colored circles.

## Ship Blockers

- [ ] Commission/create real default skin (7 expressions + idle APNGs)
- [ ] Create at least 1 additional skin (proves the system, gives choice)
- [ ] Replace placeholder app/tray icons
- [ ] First-run setup flow (token prompt on empty config, not silent failure)
- [ ] Make Get Skins work (set the Pling URL, verify flow end-to-end)
- [ ] README rewrite: user-facing setup guide (not dev-only)
- [ ] Skin creation docs (invite community from day 1)

## Should Ship (Strongly Recommended)

- [ ] AUR package (your Ring 1 audience is mostly Arch)
- [ ] Hyprland window positioning (`hyprctl` — fastest-growing compositor)
- [ ] Basic error states: show something when gateway is unreachable or token is wrong

## Defer

Everything else. Claude Code engine, sidekick/kero, voice/TTS, macOS, Windows, multi-monitor, E2E tests, animated transitions, conversation history window — all post-launch.

## Prepare Answers For

These questions will come in week 1:

1. **"Does it work with Ollama / local models?"** — Have a clear answer. r/LocalLLaMA (500k+) will ask immediately. Even "planned, here's the gateway abstraction that enables it" is fine.
2. **"Hyprland support?"** — Ship it or say "next release."
3. **"Can I customize the personality / system prompt?"** — Users want to name their character and define how it talks.
4. **"Is there a package? I don't want to compile Rust."** — AUR minimum. AppImage/Flatpak later.
5. **"Global hotkey to summon chat?"** — Keyboard shortcut to open input from anywhere.

## Launch Channels

| Channel | Why |
|---------|-----|
| Show HN | Tech-literate, appreciates novel desktop apps |
| r/unixporn | Screenshot-driven, your exact Ring 1 |
| r/linux | Broad Linux audience |
| r/swaywm, r/hyprland | Compositor-specific communities |
| r/LocalLLaMA | If Ollama support exists or is announced |
| Fosstodon / Mastodon | FOSS-friendly, Linux-heavy |

## Post-Launch Priority Queue

1. Ollama / local LLM backend (unlocks Ring 2 audience)
2. Personality customization UI (system prompt, character name)
3. More compositor support (KDE, GNOME)
4. Character memory / persistent context
5. macOS build
6. Interaction triggers (time-of-day greetings, idle variations)
