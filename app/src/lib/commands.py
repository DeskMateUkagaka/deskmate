"""Slash command data and parsing for autocomplete support."""

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_FILENAME = "commands_cache.json"
_CACHE_MAX_AGE_SECONDS = 86400  # 24 hours

# Matches: /name [optional args/aliases] - Description
_CMD_RE = re.compile(r"^(/\w+)(?:\s[^-]*)?\s+-\s+(.+)$")


@dataclass
class SlashCommand:
    name: str  # e.g., "/new"
    description: str  # e.g., "Start a new session."


def parse_commands_response(text: str) -> list[SlashCommand]:
    """Parse plain-text /commands response from gateway.

    Format:
      /name  - Description
      /name <arg> (/alias1, /alias2) - Description
    """
    commands: list[SlashCommand] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _CMD_RE.match(line)
        if m:
            name = m.group(1)
            description = m.group(2).strip()
            commands.append(SlashCommand(name=name, description=description))
    logger.debug("Parsed %d slash commands", len(commands))
    return commands


def load_cached_commands(cache_dir: Path) -> list[SlashCommand] | None:
    """Load from cache if < 24h old. Returns None if missing or stale."""
    cache_path = cache_dir / _CACHE_FILENAME
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        saved_at = data.get("saved_at", 0)
        if time.time() - saved_at > _CACHE_MAX_AGE_SECONDS:
            logger.debug("Commands cache is stale, ignoring")
            return None
        raw_commands = data.get("commands", [])
        commands = [
            SlashCommand(name=c["name"], description=c["description"]) for c in raw_commands
        ]
        logger.debug("Loaded %d commands from cache", len(commands))
        return commands
    except Exception as e:
        logger.warning("Failed to load commands cache: %s", e)
        return None


def save_cached_commands(cache_dir: Path, commands: list[SlashCommand]) -> None:
    """Save commands to cache with timestamp."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / _CACHE_FILENAME
    data = {
        "saved_at": time.time(),
        "commands": [{"name": c.name, "description": c.description} for c in commands],
    }
    try:
        cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.debug("Saved %d commands to cache at %s", len(commands), cache_path)
    except Exception as e:
        logger.warning("Failed to save commands cache: %s", e)
