import logging
import platform
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def _default_config_dir() -> Path:
    try:
        from platformdirs import user_config_dir
        return Path(user_config_dir("deskmate"))
    except ImportError:
        pass

    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "deskmate"
    if system == "Windows":
        appdata = Path(sys.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return appdata / "deskmate"
    # Linux / other
    xdg = Path(sys.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return xdg / "deskmate"


@dataclass
class QuakeTerminalConfig:
    enabled: bool = True
    hotkey: str = "ctrl+alt+`"
    terminal_emulator: str | None = None
    command: str = "openclaw tui"
    height_percent: int = 40


@dataclass
class Settings:
    gateway_url: str = "ws://127.0.0.1:18789"
    gateway_token: str = ""
    bubble_timeout_ms: int = 60000
    proactive_enabled: bool = False
    proactive_interval_mins: int = 60
    ghost_x: float = 0.0
    ghost_y: float = 0.0
    current_skin_id: str = "default"
    ghost_height_pixels: int = 540
    popup_margin_top: float = 10.0
    popup_margin_bottom: float = 10.0
    popup_margin_left: float = 10.0
    popup_margin_right: float = 10.0
    idle_interval_seconds: float = 30.0
    quake_terminal: QuakeTerminalConfig = field(default_factory=QuakeTerminalConfig)
    ghost_toggle_hotkey: str = "super+f11"


def _quake_from_dict(data: dict[str, Any]) -> QuakeTerminalConfig:
    cfg = QuakeTerminalConfig()
    if "enabled" in data:
        cfg.enabled = bool(data["enabled"])
    if "hotkey" in data:
        cfg.hotkey = str(data["hotkey"])
    if "terminal_emulator" in data:
        val = data["terminal_emulator"]
        cfg.terminal_emulator = str(val) if val is not None else None
    if "command" in data:
        cfg.command = str(data["command"])
    if "height_percent" in data:
        cfg.height_percent = int(data["height_percent"])
    return cfg


def _settings_from_dict(data: dict[str, Any]) -> Settings:
    s = Settings()
    simple_fields = [
        "gateway_url", "gateway_token", "bubble_timeout_ms",
        "proactive_enabled", "proactive_interval_mins",
        "ghost_x", "ghost_y", "current_skin_id",
        "ghost_height_pixels",
        "popup_margin_top", "popup_margin_bottom",
        "popup_margin_left", "popup_margin_right",
        "idle_interval_seconds", "ghost_toggle_hotkey",
    ]
    for f in simple_fields:
        if f in data:
            setattr(s, f, data[f])
    if "quake_terminal" in data and isinstance(data["quake_terminal"], dict):
        s.quake_terminal = _quake_from_dict(data["quake_terminal"])
    return s


def _settings_to_dict(s: Settings) -> dict[str, Any]:
    d = asdict(s)
    return d


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
            logger.info("No settings file found at %s, using defaults", self._path)
            self._settings = Settings()
            return self._settings

        try:
            contents = self._path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Failed to read settings file %s: %s", self._path, e)
            self._settings = Settings()
            return self._settings

        data = yaml.safe_load(contents)
        if not isinstance(data, dict):
            logger.warning("Settings file %s has unexpected format, using defaults", self._path)
            self._settings = Settings()
            return self._settings

        self._settings = _settings_from_dict(data)
        logger.info("Loaded settings from %s", self._path)
        return self._settings

    def save(self) -> None:
        """Save settings to YAML. Top-level comments from the existing file are preserved."""
        self._config_dir.mkdir(parents=True, exist_ok=True)

        existing_contents = ""
        if self._path.exists():
            try:
                existing_contents = self._path.read_text(encoding="utf-8")
            except OSError as e:
                logger.warning("Could not read existing settings for comment preservation: %s", e)

        header, key_comments, trailer = _extract_comments(existing_contents)

        data = _settings_to_dict(self._settings)
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
        logger.info("Saved settings to %s", self._path)

    def update(self, **kwargs: Any) -> Settings:
        """Update specific fields and save. Returns the updated Settings."""
        for key, value in kwargs.items():
            if not hasattr(self._settings, key):
                raise ValueError(f"Unknown settings field: {key!r}")
            setattr(self._settings, key, value)
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
            line
            and not line[0].isspace()
            and ":" in trimmed
            and not trimmed.startswith("#")
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
