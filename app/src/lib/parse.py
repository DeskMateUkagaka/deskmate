import re


def parse_emotion(text: str) -> str:
    """Extract the last [emotion:X] tag from text. Returns 'neutral' if none found."""
    matches = re.findall(r"\[emotion:(\w+)\]", text)
    return matches[-1] if matches else "neutral"


def strip_emotion_tags(text: str) -> str:
    """Remove all [emotion:X] tags from text."""
    return re.sub(r"\[emotion:\w+\]", "", text).strip()


def parse_buttons(text: str) -> list[str]:
    """Extract button labels from [btn:message] tags in text."""
    return re.findall(r"\[btn:([^\]]+)\]", text)


def strip_button_tags(text: str) -> str:
    """Remove all [btn:X] tags from text."""
    return re.sub(r"\[btn:[^\]]+\]", "", text).strip()


def strip_all_tags(text: str) -> str:
    """Remove all custom tags ([emotion:...], [btn:...]) from text."""
    text = strip_emotion_tags(text)
    text = strip_button_tags(text)
    return text
