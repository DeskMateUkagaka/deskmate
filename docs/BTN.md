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
4. Buttons appear to the LEFT of Copy / Pin / Dismiss
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
  → useOpenClaw: strips tags from display, parses buttons on final
  → App.tsx: captures bubble ID before finalize(), sets buttons after
  → BubbleWindow: renders buttons left of Copy/Pin/Dismiss
  → User clicks → bubble-action event { action: 'button-click', message }
  → App.tsx: clearButtons + sendMessage
```

## Implementation Details

### Parsing (`useOpenClaw.ts`)

- `parseButtons(text)` — regex `/\[btn:([^\]]+)\]/g`, returns first 3 trimmed non-empty labels
- `stripButtonTags(text)` — regex `/\[btn:[^\]]+\]/g`, removes all tags
- Tags stripped during streaming (delta handler) so they never flash in the bubble
- Buttons only extracted on finalization (final handler)

### State (`useBubble.ts`)

- `BubbleItem.buttons: string[]` — empty during streaming, populated on finalize
- `setButtons(id, buttons)` — takes explicit ID (not activeBubbleIdRef, which is null after finalize)
- `clearButtons(id)` — sets buttons to `[]` for a specific item

### Rendering (`BubbleWindow.tsx`)

- Dynamic buttons rendered when `!item.isStreaming && item.buttons.length > 0`
- Styled with `primaryPillStyle` (same as Copy/Pin)
- `itemSignature` includes button content so the bubble resizes correctly when buttons are added/removed

### Orchestration (`App.tsx`)

- Finalization effect captures `getActiveBubbleId()` BEFORE `finalize()`, then calls `setButtons` with the captured ID
- Uses `currentButtonsRef` (not state) to avoid re-triggering the effect on button state changes
- Button click handler also closes the chat-input popup to prevent double-sends

## Debug Shortcut

Type `btn` in the chat input to test. Shows "Here are some options for you" with 3 buttons: Tell me more, Thanks, Goodbye.

## Known Limitations

- In-band parsing is fragile — the AI must be prompted to emit `[btn:...]` tags correctly (same fragility as the emotion system)
- Button labels containing `]` will break parsing (the regex stops at the first `]`)
- No separate label vs. message — the button text IS the message sent to the AI
- Auto-dismiss timer is unaffected by buttons; if it fires, buttons disappear with the bubble
