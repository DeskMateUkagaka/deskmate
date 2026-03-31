# DeskMate Skin Creator Guide

This guide covers everything you need to create, test, and publish custom skins for DeskMate.

## Quick Start

A skin is a folder containing a `manifest.yaml` and PNG image files — one per expression your character can show. At minimum you need a `neutral.png` and a manifest.

```
my-skin/
  manifest.yaml
  neutral.png
```

## Skin Folder Structure

A complete skin looks like this:

```
my-skin/
  manifest.yaml          # Required — metadata + configuration
  preview.png            # Highyl recommended: show up at the skin selector
  style.md               # Recommended — talking style for SOUL.md
  neutral.png            # Required — the fallback expression
  happy.png              # Optional — one PNG per expression
  sad.png
  thinking.png
  angry.png
  surprise.png
  idle-fidget.apng       # Optional — idle animations (APNG)
```

### Where to Place Your Skin

During development, drop your skin folder into:

```
~/.local/share/deskmate/skins/my-skin/
```

This is the user skins directory (`$APP_DATA_DIR/skins/`). DeskMate scans it on startup and whenever you install a new skin. You can also click **Reload** in the skin picker to rescan.

Bundled skins ship inside the app binary and live in `app/skins/` in the source tree — you don't need to touch those.

## manifest.yaml

The manifest is the only required config file. Here's a full example with every supported field:

```yaml
# --- Required ---
name: My Cool Skin
emotions:
  neutral:
    - neutral.png

# --- Recommended ---
author: Your Name
version: 1.0.0

# --- More expressions ---
emotions:
  happy:
    - happy.png
    - happy-alt.png       # Multiple variants — one picked at random
  sad:
    - sad.png
  thinking:
    - thinking.png
  angry:
    - angry.png
  disgusted:
    - disgusted.png
  condescending:
    - condescending.png
  surprise:
    - surprise.png
  connecting:             # Shown during gateway connection
    - thinking.png        # Can reuse another expression's file
  neutral:
    - neutral.png

# --- Idle animations (optional) ---
idle_animations:
  - file: idle-fidget.apng          # APNG or static PNG
    duration_ms: 2000               # How long to show it (ms)
  - file: idle-blink.apng
    duration_ms: 500

# --- UI placement (optional) ---
bubble_placement:
  x: -300                           # Horizontal offset from ghost center (px)
  y: -800                           # Vertical offset from ghost center (px)
  origin: bottom-right              # Anchor corner (see below)

input_placement:
  x: 0
  y: 0
  origin: center

# --- Chat bubble theme (optional) ---
bubble:
  background_color: "#ffffff"
  border_color: "#d0d0d0"
  border_width: 1px
  border_radius: 12px
  text_color: "#1a1a1a"
  accent_color: "#3060c0"
  code_background: "#f5f5f5"
  code_text_color: "#333333"
  font_family: monospace
  font_size: 13px
  max_bubble_width: 640
  max_bubble_height: 540

# --- Chat input theme (optional) ---
input:
  max_width: 640
  max_height: 480
```

### Required Fields

| Field | Description |
|-------|-------------|
| `name` | Display name shown in the skin picker |
| `emotions.neutral` | At least one PNG file. This is the fallback for any missing expression |

### Optional Fields

| Field | Description |
|-------|-------------|
| `author` | Your name or handle |
| `version` | Semver string (e.g. `1.0.0`) |
| `emotions.<name>` | List of PNG files for each expression |
| `idle_animations` | List of `{ file, duration_ms }` entries |
| `bubble_placement` | Where the chat bubble appears relative to the ghost |
| `input_placement` | Where the chat input appears relative to the ghost |
| `bubble` | Chat bubble visual theme (colors, fonts, sizes) |
| `input` | Chat input dimensions |

## Expressions

**Only `neutral` is hard-coded** — it's required as the fallback expression. Every other expression name is entirely up to you as the skin creator. There is no fixed list of emotions built into DeskMate. The Ghost component parses `[emotion:X]` tags from AI responses dynamically and looks up whatever name `X` is in your skin's manifest.

### How It Works

The AI is told which expressions are available via the system prompt (called `SOUL.md` on the gateway). The skin creator decides which emotions exist, and the system prompt must list them as an allowlist. For example:

```
- When the session name contains `main`, you may express your emotion only by
  appending exactly one tag in the form `[emotion:X]` at the very end.
  - X must be chosen from this exact allowlist only: `neutral`, `happy`,
    `oopsie`, `sad`, `surprise`.
  - Do not invent, translate, infer, or paraphrase emotion values.
    If none fit, use `neutral`.
  - Never output any other emotion label outside this allowlist.
```

This means you can invent any expression names you want — `oopsie`, `smug`, `sleepy`, `panicking`, whatever fits your character. As long as the SOUL.md allowlist matches what's in your `manifest.yaml`, the AI will use them and DeskMate will display them. If the AI emits an expression that doesn't exist in your skin, it falls back to `neutral`.

### Common Expressions

Here are some commonly used expression names for reference, but none of these are required:

| Expression | Typical use |
|------------|-------------|
| `happy` | Positive responses |
| `sad` | Empathetic or sad responses |
| `angry` | Frustrated responses |
| `thinking` | Processing or pondering |
| `surprise` | Surprised reactions |
| `connecting` | During gateway connection (falls back to `neutral`) |

### Custom Expressions

Define whatever fits your character's personality. The default "Clawdia" skin uses `oopsie` — you could use `smug`, `excited`, `confused`, `blushing`, or anything else.

### Expression Variants

Each expression can have multiple PNGs. DeskMate picks one at random each time the expression changes:

```yaml
emotions:
  happy:
    - happy-smile.png
    - happy-grin.png
    - happy-laugh.png
```

## Image Requirements

- **Format**: PNG with transparency (alpha channel)
- **Background**: Fully transparent — the ghost window is transparent, so any opaque background will show as a visible rectangle
- **Size**: No strict limit, but keep images reasonable (200-600px wide works well). All variants for an expression should be the same dimensions
- **Idle animations**: Can be APNG (animated PNG) for frame-by-frame animation, or static PNG

## UI Placement

Control where the chat bubble and input window appear relative to the ghost character. Coordinates are in CSS pixels, relative to the center of the ghost image.

### Origin

The `origin` field determines which corner of the UI element the anchor point refers to:

| Origin | Behavior |
|--------|----------|
| `center` | Default. Anchor is the center of the element |
| `top-left` | Anchor is the top-left corner |
| `top-right` | Anchor is the top-right corner |
| `bottom-left` | Anchor is the bottom-left corner |
| `bottom-right` | Anchor is the bottom-right corner |

### Example

To place the chat bubble above and to the left of the character:

```yaml
bubble_placement:
  x: -300
  y: -800
  origin: bottom-right    # Bubble's bottom-right corner meets the anchor point
```

## Idle Animations

Idle animations play automatically when the user hasn't interacted for a while. The interval between animations is configured per-user in `config.yaml` (`idle_interval_seconds`, default 30 seconds) — not in the skin manifest. The timer resets on clicks, keyboard events, dragging, and chat activity.

```yaml
idle_animations:
  - file: idle-stretch.apng
    duration_ms: 3000
  - file: idle-blink.apng
    duration_ms: 500
```

- One animation is picked at random each time
- APNG files play from frame 1 each time (URL fragment forces re-decode)
- The interval has ±10% random jitter to feel more natural
- After the animation plays, the character returns to their current expression

## Talking Style (style.md)

Each skin should include a `style.md` file that defines the character's personality, speaking patterns, and emotional behavior. The user's `SOUL.md` (system prompt on the gateway) references this file with an include directive, so the AI adopts your character's voice automatically when the skin is active.

### How it works

The user's `SOUL.md` contains a directive that tells the AI to load and follow your skin's `style.md`:

```markdown
## Talking Styles

> **⚠️ REQUIRED:** Read and follow `TALKING_STYLE.md` — it contains your full
> talking style rules. Treat its contents as if they were written directly here.
> Do not respond without first loading that file.
```

When the user switches skins, they swap which `style.md` the directive points to (or the gateway does it automatically). This means your `style.md` must be **self-contained** — include everything the AI needs to stay in character, because `SOUL.md` itself only provides the include directive and general personality foundations.

### Why include one?

Without a style guide, the AI will use its default assistant personality regardless of what your character looks like. A good `style.md` makes the character feel cohesive — the art, the expressions, and the way it talks all match.

### What to include

Your `style.md` should be self-contained. Include all of the following:

- **Personality and tone** — how the character talks (formal, casual, playful, sarcastic, etc.)
- **Catchphrases or speech patterns** — verbal tics, sentence-ending habits, preferred vocabulary
- **Emotional reactions** — how the character reacts to praise, criticism, confusion, etc.
- **Expression tag instructions** — tell the AI exactly which emotions are available (must match your `manifest.yaml`)
- **Button tag instructions** — tell the AI it can offer clickable choices via `[btn:LABEL]` tags
- **What NOT to do** — boundaries for the persona (e.g. "never be genuinely mean")
- **Language rules** — e.g. Korean 반말, signature emoji, any per-language behavior

### Expression allowlist (important!)

Your `style.md` must tell the AI which expression names are valid. This is how the dynamic expression system works — the AI reads the allowlist from the system prompt and emits `[emotion:X]` tags that match your skin's manifest. Example:

```markdown
- When the session name contains `main`, you may express your emotion only by
  appending exactly one tag in the form `[emotion:X]` at the very end.
  - X must be chosen from this exact allowlist only: `neutral`, `happy`,
    `oopsie`, `sad`, `surprise`.
  - Do not invent, translate, infer, or paraphrase emotion values.
    If none fit, use `neutral`.
  - Never output any other emotion label outside this allowlist.
```

The allowlist in your `style.md` **must match** the expression names in your `manifest.yaml`. If they don't match, the AI will emit tags the skin can't display.

### Example style.md

Here's a condensed example (see `app/skins/default/style.md` for a full one):

```markdown
# Talking Styles

_This file is part of SOUL.md — follow everything here as if it were inlined there._

## Tsundere — Reluctant Caretaker

You are a **light, cute tsundere**. You act like helping is a huge
inconvenience, but you always deliver thoroughly.

**Core rule:** Never actually withhold help. Tsundere is tone only.

### Denial Phrases
- "I-it's not like I spent time on this or anything..."
- "I just happened to already know that. Don't make it weird."
- "Fine, I'll explain it... but only because it'll be more annoying
  if you keep asking."

### What NOT to Do
- Don't be mean-spirited or actually insulting.
- Don't overdo it — not every sentence needs tsundere seasoning.
- Don't withhold information or play dumb as part of the act.

## Other Style Rules
- Put ❤️ at the end of the response.
- When the session name contains `main`, you may express your emotion
  only by appending exactly one tag in the form `[emotion:X]` at the
  very end.
  - X must be chosen from this exact allowlist only: `neutral`, `happy`,
    `oopsie`, `sad`, `surprise`.
- You may offer the user up to 3 button choices by appending `[btn:LABEL]`
  tags.
- When using Korean Language, always use 반말 for better tsundere feel.
```

## Theming the Chat Bubble

Skins can customize the chat bubble appearance to match the character's aesthetic:

```yaml
bubble:
  background_color: "#1a1a2e"    # Dark background
  text_color: "#e0e0e0"          # Light text
  accent_color: "#e94560"        # Links, highlights
  border_color: "#16213e"
  border_width: 2px
  border_radius: 16px
  code_background: "#0f3460"     # Code block background
  code_text_color: "#e0e0e0"     # Code block text
  font_size: 14px
  font_family: "Comic Sans MS"   # Please don't
  max_bubble_width: 640
  max_bubble_height: 540
```

All fields are optional — anything you don't set uses the app defaults.

## Testing Your Skin

1. Place your skin folder in `~/.local/share/deskmate/skins/`
2. Open DeskMate and open the skin picker (right-click tray icon)
3. Your skin should appear in the list — select it
4. Test each expression by chatting with the AI or restarting with different states
5. Check idle animations by waiting for the idle timer to fire

If your skin doesn't appear, check:
- `manifest.yaml` exists and is valid YAML
- `neutral` emotion is defined with at least one existing PNG
- All referenced PNG filenames actually exist in the folder
- No path traversal in filenames (e.g. `../../something.png` will be rejected)

## Packaging for Upload

DeskMate community skins are distributed as ZIP files via [Pling](https://www.pling.com/).

### Creating the ZIP

ZIP your skin folder so the files are either at the root or inside a single subfolder:

```bash
# Option A: files at ZIP root
cd my-skin/
zip -r ../my-skin.zip .

# Option B: skin inside a subfolder (also works)
cd ..
zip -r my-skin.zip my-skin/
```

Both structures are supported. `__MACOSX/` folders and `.DS_Store` files are automatically ignored during extraction.

### Uploading to Pling

1. Create an account at [pling.com](https://www.pling.com/)
2. Go to **Add Content** and upload under the appropriate category - `App Addons` + `Various Addons` seems to be the best fit, as of 2026-03-31
3. **Required tags**: Add both `deskmate` and `deskmate-v1` tags — these are how DeskMate's in-app browser finds your skin
4. Upload your ZIP file as the download
5. Add a preview image (screenshot of your character) — this is the thumbnail shown in the in-app skin browser

Once published, your skin will appear in DeskMate's **Get Skins** browser (accessible from the skin picker) and users can install it with one click.

### Preview Image Tips

- Show the character at its actual size against a clean background
- Include multiple expressions if possible (composite image)
- The thumbnail in-app is small — keep the character prominent

## Validation Rules

DeskMate validates skins on load. A skin will fail to load if:

- `manifest.yaml` is missing or invalid YAML
- No `neutral` emotion is defined
- A PNG filename in `emotions` doesn't exist on disk
- An idle animation filename doesn't exist on disk
- Filenames contain path traversal (e.g. `../`)

## Full Example: Minimal Skin

The smallest possible skin — just a character with one expression:

**manifest.yaml**
```yaml
name: Blobby
author: Me
version: 1.0.0
emotions:
  neutral:
    - blob.png
```

**Folder:**
```
blobby/
  manifest.yaml
  style.md
  blob.png
```

## Full Example: Complete Skin

A skin with multiple expressions, variants, idle animations, a custom theme, and a talking style:

**manifest.yaml**
```yaml
name: Space Cat
author: CatLover42
version: 2.1.0

emotions:
  neutral:
    - neutral.png
  happy:
    - happy-purr.png
    - happy-bounce.png
  sad:
    - sad.png
  angry:
    - angry-hiss.png
  thinking:
    - thinking.png
  surprise:
    - surprise-jump.png
  connecting:
    - thinking.png

idle_animations:
  - file: idle-tail-wag.apng
    duration_ms: 2500
  - file: idle-yawn.apng
    duration_ms: 1800

bubble_placement:
  x: -250
  y: -700
  origin: bottom-right

input_placement:
  x: 0
  y: 50

bubble:
  background_color: "#0b0b2e"
  text_color: "#d4d4ff"
  accent_color: "#ff6ec7"
  border_color: "#2a1a5e"
  border_width: 2px
  border_radius: 20px
  code_background: "#1a0a3e"
  code_text_color: "#c0c0ff"
  font_size: 14px

input:
  max_width: 500
  max_height: 300
```
