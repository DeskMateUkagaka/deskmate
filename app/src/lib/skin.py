import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class UiPlacement:
    x: float = 0.0
    y: float = 0.0
    origin: str = "center"  # center, top-left, top-right, bottom-left, bottom-right
    margin_x: float = 10.0
    margin_y: float = 10.0


@dataclass
class BubbleTheme:
    background_color: str | None = None
    border_color: str | None = None
    border_width: str | None = None
    border_radius: str | None = None
    text_color: str | None = None
    accent_color: str | None = None
    code_background: str | None = None
    code_text_color: str | None = None
    font_family: str | None = None
    font_size: str | None = None
    max_bubble_width: int | None = None
    max_bubble_height: int | None = None


@dataclass
class IdleAnimation:
    file: str
    duration_ms: int


@dataclass
class SkinInfo:
    id: str
    name: str
    path: Path
    author: str = ""
    version: str = "1.0"
    description: str | None = None
    emotions: list[str] = field(default_factory=list)
    bubble_placement: UiPlacement | None = None
    input_placement: UiPlacement | None = None
    bubble_theme: BubbleTheme | None = None
    idle_animations: list[IdleAnimation] = field(default_factory=list)
    source: str = "bundled"  # bundled | community
    format_version: int = 1


def _parse_ui_placement(data: dict[str, Any]) -> UiPlacement:
    p = UiPlacement()
    if "x" in data:
        p.x = float(data["x"])
    if "y" in data:
        p.y = float(data["y"])
    if "origin" in data:
        p.origin = str(data["origin"])
    if "margin_x" in data:
        p.margin_x = float(data["margin_x"])
    if "margin_y" in data:
        p.margin_y = float(data["margin_y"])
    return p


def _parse_bubble_theme(data: dict[str, Any]) -> BubbleTheme:
    t = BubbleTheme()
    str_fields = [
        "background_color",
        "border_color",
        "border_width",
        "border_radius",
        "text_color",
        "accent_color",
        "code_background",
        "code_text_color",
        "font_family",
        "font_size",
    ]
    for f in str_fields:
        if f in data and data[f] is not None:
            setattr(t, f, str(data[f]))
    if "max_bubble_width" in data and data["max_bubble_width"] is not None:
        t.max_bubble_width = int(data["max_bubble_width"])
    if "max_bubble_height" in data and data["max_bubble_height"] is not None:
        t.max_bubble_height = int(data["max_bubble_height"])
    return t


def _load_manifest(skin_id: str, skin_path: Path, source: str) -> SkinInfo:
    manifest_path = skin_path / "manifest.yaml"
    contents = manifest_path.read_text(encoding="utf-8")
    data: dict[str, Any] = yaml.safe_load(contents)

    if not isinstance(data, dict):
        raise ValueError(f"manifest.yaml for skin '{skin_id}' is not a YAML mapping")

    emotions_raw: dict[str, list[str]] = data.get("emotions", {})
    if not isinstance(emotions_raw, dict):
        raise ValueError(f"'emotions' in skin '{skin_id}' must be a mapping")

    if "neutral" not in emotions_raw:
        raise ValueError(f"Skin '{skin_id}' is missing required emotion 'neutral'")

    # Validate emotion PNG lists are non-empty
    for emotion, files in emotions_raw.items():
        if not files:
            raise ValueError(f"Emotion '{emotion}' in skin '{skin_id}' has no files")

    bubble_placement: UiPlacement | None = None
    if isinstance(data.get("bubble_placement"), dict):
        bubble_placement = _parse_ui_placement(data["bubble_placement"])

    input_placement: UiPlacement | None = None
    if isinstance(data.get("input_placement"), dict):
        input_placement = _parse_ui_placement(data["input_placement"])

    bubble_theme: BubbleTheme | None = None
    bubble_raw = data.get("bubble")
    if isinstance(bubble_raw, dict):
        bubble_theme = _parse_bubble_theme(bubble_raw)

    idle_animations: list[IdleAnimation] = []
    for anim in data.get("idle_animations", []):
        if not isinstance(anim, dict):
            continue
        anim_file = str(anim.get("file", ""))
        anim_dur = int(anim.get("duration_ms", 0))
        if not anim_file or anim_dur == 0:
            raise ValueError(
                f"Idle animation in skin '{skin_id}' missing 'file' or has duration_ms=0"
            )
        idle_animations.append(IdleAnimation(file=anim_file, duration_ms=anim_dur))

    return SkinInfo(
        id=skin_id,
        name=str(data.get("name", skin_id)),
        path=skin_path,
        author=str(data.get("author", "")) if data.get("author") is not None else "",
        version=str(data.get("version", "1.0")) if data.get("version") is not None else "1.0",
        description=str(data["description"]) if data.get("description") is not None else None,
        emotions=list(emotions_raw.keys()),
        bubble_placement=bubble_placement,
        input_placement=input_placement,
        bubble_theme=bubble_theme,
        idle_animations=idle_animations,
        source=source,
        format_version=int(data.get("format_version", 1)),
    )


class SkinLoader:
    def __init__(self, skins_dir: Path):
        self._skins_dir = skins_dir

    def list_skins(self) -> list[SkinInfo]:
        """Scan skins directory and return all valid skins."""
        skins: list[SkinInfo] = []
        if not self._skins_dir.exists():
            logger.warning("Skins directory not found: %s", self._skins_dir)
            return skins

        for entry in sorted(self._skins_dir.iterdir()):
            if not entry.is_dir():
                continue
            if not (entry / "manifest.yaml").exists():
                continue
            skin_id = entry.name
            try:
                info = _load_manifest(skin_id, entry, "bundled")
                skins.append(info)
                logger.info("Loaded skin: %s (%s) [bundled]", info.name, skin_id)
            except Exception as e:
                logger.warning("Failed to load skin at %s: %s", entry, e)

        return skins

    def load_skin(self, skin_id: str) -> SkinInfo:
        """Load a specific skin by ID. Raises FileNotFoundError or ValueError on failure."""
        skin_path = self._skins_dir / skin_id
        if not skin_path.is_dir():
            raise FileNotFoundError(f"Skin directory not found: {skin_path}")
        manifest_path = skin_path / "manifest.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest.yaml not found in skin '{skin_id}'")
        return _load_manifest(skin_id, skin_path, "bundled")

    def get_emotion_images(self, skin: SkinInfo, emotion: str) -> list[Path]:
        """Return all image variant Paths for the given emotion.

        Falls back to 'neutral' if the emotion is not present in the manifest.
        """
        manifest_path = skin.path / "manifest.yaml"
        contents = manifest_path.read_text(encoding="utf-8")
        data: dict[str, Any] = yaml.safe_load(contents)
        emotions_raw: dict[str, list[str]] = data.get("emotions", {})

        resolved = emotion if emotion in emotions_raw else "neutral"
        files = emotions_raw.get(resolved, [])
        return [skin.path / f for f in files]

    def get_preview_image(self, skin_id: str) -> Path | None:
        """Return the path to preview.png for the skin picker, or None if absent."""
        preview = self._skins_dir / skin_id / "preview.png"
        return preview if preview.exists() else None
