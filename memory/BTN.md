# Dynamic Button Tags

The AI can embed clickable buttons in chat responses using `[btn:msg]` tags, similar to the `[emotion:X]` expression system. Buttons appear in the chat bubble and send the msg text to the AI when clicked.

## Tag Syntax

```
[btn:Tell me more]
[btn:Thanks]
[btn:What else?]
```

- Tags are stripped from the displayed text (never shown as raw text)
- Up to 3 buttons per message; extras are silently dropped
- `msg` can contain spaces and punctuation (anything except `]`)
- Whitespace-only labels are filtered out

## How It Works

1. AI response text contains `[btn:msg]` tags anywhere in the content
2. Tags are stripped during streaming so they never appear as raw text
3. After streaming finalizes, buttons are extracted and rendered in the bubble
4. Buttons appear in the bubble's action button row
5. Clicking a button:
   - Removes all dynamic buttons from that bubble
   - Sends the button's `msg` as a new chat message to the AI
   - Keeps the bubble text visible (does not dismiss)
6. If the bubble auto-dismisses or the user clicks Dismiss, buttons simply disappear

## Interaction with Emotions

Both tag types can coexist in the same message:

```
Here are your options [emotion:happy] [btn:Option A][btn:Option B]
```

- `[emotion:X]` — the LAST emotion tag in the text is applied to the ghost
- `[btn:msg]` — first 3 tags become buttons, all are stripped from display

## Data Flow

```
AI text with [btn:X]
  → parse.py: strip_all_tags() removes from display, parse_buttons() extracts labels on final
  → main.py: captures bubble ID before finalize(), sets buttons after
  → BubbleWindow JS: renders buttons via setButtons()
  → User clicks → QWebChannel bridge → action signal { 'button-click', item_id, message }
  → main.py: _on_bubble_action() → re-sends message as new chat
```

## Implementation

### Parsing (`app/src/lib/parse.py`)

- `parse_buttons(text)` — regex `\[btn:([^\]]+)\]`, returns all trimmed non-empty labels
- `strip_button_tags(text)` — regex `\[btn:[^\]]+\]`, removes all tags
- `strip_all_tags(text)` — strips both emotion and button tags

### Rendering (`app/src/windows/bubble.py`)

- Buttons rendered via JS `setButtons(itemId, buttonsJson)` in the embedded HTML
- Click handler calls `bridge.onAction(JSON.stringify({itemId, message}))` via QWebChannel
- `_BubbleBridge` forwards to `BubbleWindow.action` signal

### Orchestration (`app/main.py`)

- `_on_chat_event()`: on "final" state, calls `parse_buttons()` then `bubble.set_buttons()`
- `_on_bubble_action()`: on "button-click" action, re-sends button message via `_on_chat_send()`

## Known Limitations

- In-band parsing is fragile — the AI must be prompted to emit `[btn:...]` tags correctly (same fragility as the emotion system)
- Button labels containing `]` will break parsing (the regex stops at the first `]`)
- No separate label vs. message — the button text IS the message sent to the AI
- Auto-dismiss timer is unaffected by buttons; if it fires, buttons disappear with the bubble
