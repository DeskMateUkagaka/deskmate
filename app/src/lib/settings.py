import platform
import sys
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from platformdirs import user_config_dir
from pydantic import BaseModel


def _default_config_dir() -> Path:
    return Path(user_config_dir("deskmate"))


class QuakeTerminalConfig(BaseModel):
    enabled: bool = True
    hotkey: str = "ctrl+alt+`"
    terminal_emulator: str | None = None
    command: str = "openclaw tui"
    height_percent: int = 40


class Settings(BaseModel):
    gateway_url: str = "ws://127.0.0.1:18789"
    gateway_token: str = ""
    bubble_timeout_ms: int = 30000
    proactive_enabled: bool = False
    proactive_interval_mins: int = 60
    current_skin_id: str = "default"
    ghost_height_pixels: int = 540
    popup_margin_top: float = 10.0
    popup_margin_bottom: float = 10.0
    popup_margin_left: float = 10.0
    popup_margin_right: float = 10.0
    idle_interval_seconds: float = 30.0
    quake_terminal: QuakeTerminalConfig = QuakeTerminalConfig()
    ghost_toggle_hotkey: str = "super+f11"


class AppState(BaseModel):
    """Transient app state (window positions, etc.) — stored in state.yaml, not config.yaml."""

    ghost_x: float = 0.0
    ghost_y: float = 0.0


class AppStateManager:
    """Manages transient state in state.yaml, separate from user config."""

    def __init__(self, config_dir: Path | None = None):
        self._config_dir = config_dir if config_dir is not None else _default_config_dir()
        self._path = self._config_dir / "state.yaml"
        self._state = AppState()

    def load(self) -> AppState:
        if self._path.exists():
            try:
                data = yaml.safe_load(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._state = AppState.model_validate(data)
            except Exception as e:
                logger.warning(f"Failed to read state file {self._path}: {e}")
        return self._state

    def save(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        data = self._state.model_dump()
        self._path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")

    def update(self, **kwargs: Any) -> AppState:
        self._state = self._state.model_copy(update=kwargs)
        self.save()
        return self._state

    @property
    def state(self) -> AppState:
        return self._state


class SettingsManager:
    def __init__(self, config_dir: Path | None = None):
        self._config_dir = config_dir if config_dir is not None else _default_config_dir()
        self._settings = Settings()
        self._path = self._config_dir / "config.yaml"

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> Settings:
        """Load from YAML, return defaults if missing or unreadable."""
        if not self._path.exists():
            logger.info(f"No settings file found at {self._path}, using defaults")
            self._settings = Settings()
            return self._settings

        try:
            contents = self._path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning(f"Failed to read settings file {self._path}: {e}")
            self._settings = Settings()
            return self._settings

        data = yaml.safe_load(contents)
        if not isinstance(data, dict):
            logger.warning(f"Settings file {self._path} has unexpected format, using defaults")
            self._settings = Settings()
            return self._settings

        self._settings = Settings.model_validate(data)
        logger.info(f"Loaded settings from {self._path}")
        return self._settings

    def save(self) -> None:
        """Save settings to YAML. Top-level comments from the existing file are preserved."""
        self._config_dir.mkdir(parents=True, exist_ok=True)

        existing_contents = ""
        if self._path.exists():
            try:
                existing_contents = self._path.read_text(encoding="utf-8")
            except OSError as e:
                logger.warning(f"Could not read existing settings for comment preservation: {e}")

        header, key_comments, trailer = _extract_comments(existing_contents)

        data = self._settings.model_dump()
        raw_yaml = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)

        output_lines: list[str] = []
        output_lines.extend(header)

        for line in raw_yaml.splitlines():
            # Detect top-level key lines (not indented)
            if line and not line[0].isspace() and ":" in line:
                key = line.split(":")[0].strip()
                if key in key_comments:
                    preceding, inline = key_comments[key]
                    output_lines.extend(preceding)
                    if inline:
                        output_lines.append(line + "  " + inline)
                        continue
            output_lines.append(line)

        output_lines.extend(trailer)

        text = "\n".join(output_lines) + "\n"
        self._path.write_text(text, encoding="utf-8")
        logger.info(f"Saved settings to {self._path}")

    def update(self, **kwargs: Any) -> Settings:
        """Update specific fields and save. Returns the updated Settings."""
        self._settings = self._settings.model_copy(update=kwargs)
        self.save()
        return self._settings

    @property
    def settings(self) -> Settings:
        return self._settings


# ---------------------------------------------------------------------------
# Comment extraction (mirrors the Rust extract_comments logic)
# ---------------------------------------------------------------------------


def _extract_comments(
    contents: str,
) -> tuple[list[str], dict[str, tuple[list[str], str | None]], list[str]]:
    """Parse an existing YAML file and extract human-written comments.

    Returns:
        header:       Comment/blank lines before the first key.
        key_comments: Maps top-level key -> (preceding comment lines, inline comment).
        trailer:      Trailing comment/blank lines after the last key.
    """
    header: list[str] = []
    key_comments: dict[str, tuple[list[str], str | None]] = {}
    pending: list[str] = []
    seen_any_key = False

    for line in contents.splitlines():
        trimmed = line.strip()
        is_top_key = (
            line and not line[0].isspace() and ":" in trimmed and not trimmed.startswith("#")
        )

        if is_top_key:
            key = trimmed.split(":")[0].strip()
            # Detect inline comment: value part contains " #"
            value_part = trimmed.split(":", 1)[1] if ":" in trimmed else ""
            inline_pos = value_part.find(" #")
            inline = value_part[inline_pos:].strip() if inline_pos != -1 else None
            seen_any_key = True
            key_comments[key] = (list(pending), inline)
            pending.clear()
        elif not trimmed or trimmed.startswith("#"):
            if seen_any_key:
                pending.append(line)
            else:
                header.append(line)

    trailer = list(pending)
    return header, key_comments, trailer
