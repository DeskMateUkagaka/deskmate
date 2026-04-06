import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from platformdirs import user_data_dir


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
class Live2dExpressionEntry:
    expression: str
    motion_group: str | None = None
    motion_index: int | None = None


@dataclass
class Live2dConfig:
    model: str  # path to .model3.json relative to skin dir
    scale: float = 1.0
    anchor_x: float = 0.5
    anchor_y: float = 0.5
    idle_motion_group: str = "idle"
    lip_sync: bool = False
    lip_sync_param: str = "ParamMouthOpenY"
    expressions: dict[str, list[Live2dExpressionEntry]] = field(default_factory=dict)


@dataclass
class SkinInfo:
    id: str
    name: str
    path: Path
    author: str = ""
    version: str = "1.0"
    description: str | None = None
    emotions: list[str] = field(default_factory=list)
    type: str = "static"  # static | live2d
    live2d_config: Live2dConfig | None = None
    bubble_placement: UiPlacement | None = None
    input_placement: UiPlacement | None = None
    bubble_theme: BubbleTheme | None = None
    idle_animations: list[IdleAnimation] = field(default_factory=list)
    source: str = "bundled"  # bundled | community
    format_version: int = 1
    store_provider: str = ""
    store_content_id: str = ""


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


def _parse_live2d_config(data: dict[str, Any], skin_id: str, skin_path: Path) -> Live2dConfig:
    live2d_raw = data.get("live2d")
    if not isinstance(live2d_raw, dict):
        raise ValueError(f"Skin '{skin_id}' has type 'live2d' but no 'live2d' block in manifest")

    model = live2d_raw.get("model")
    if not model:
        raise ValueError(f"Skin '{skin_id}' live2d block missing required 'model' path")
    model_path = skin_path / model
    if not model_path.exists():
        raise ValueError(f"Skin '{skin_id}' live2d model not found: {model_path}")

    expressions: dict[str, list[Live2dExpressionEntry]] = {}
    for emotion, entries in live2d_raw.get("expressions", {}).items():
        if not isinstance(entries, list):
            entries = [entries]
        expr_list = []
        for entry in entries:
            if isinstance(entry, dict):
                expr_list.append(Live2dExpressionEntry(
                    expression=str(entry.get("expression", "")),
                    motion_group=entry.get("motion_group"),
                    motion_index=entry.get("motion_index"),
                ))
            elif isinstance(entry, str):
                expr_list.append(Live2dExpressionEntry(expression=entry))
        if expr_list:
            expressions[emotion] = expr_list

    if "neutral" not in expressions:
        raise ValueError(f"Live2D skin '{skin_id}' missing required 'neutral' expression mapping")

    return Live2dConfig(
        model=str(model),
        scale=float(live2d_raw.get("scale", 1.0)),
        anchor_x=float(live2d_raw.get("anchor_x", 0.5)),
        anchor_y=float(live2d_raw.get("anchor_y", 0.5)),
        idle_motion_group=str(live2d_raw.get("idle_motion_group", "idle")),
        lip_sync=bool(live2d_raw.get("lip_sync", False)),
        lip_sync_param=str(live2d_raw.get("lip_sync_param", "ParamMouthOpenY")),
        expressions=expressions,
    )


def _load_manifest(skin_id: str, skin_path: Path, source: str) -> SkinInfo:
    manifest_path = skin_path / "manifest.yaml"
    contents = manifest_path.read_text(encoding="utf-8")
    data: dict[str, Any] = yaml.safe_load(contents)

    if not isinstance(data, dict):
        raise ValueError(f"manifest.yaml for skin '{skin_id}' is not a YAML mapping")

    skin_type = str(data.get("type", "static"))

    # For live2d skins, parse the live2d config and derive emotions from expression keys
    live2d_config: Live2dConfig | None = None
    if skin_type == "live2d":
        live2d_config = _parse_live2d_config(data, skin_id, skin_path)
        emotions_list = list(live2d_config.expressions.keys())
    else:
        # Static skin: validate emotions as before
        emotions_raw: dict[str, list[str]] = data.get("emotions", {})
        if not isinstance(emotions_raw, dict):
            raise ValueError(f"'emotions' in skin '{skin_id}' must be a mapping")

        if "neutral" not in emotions_raw:
            raise ValueError(f"Skin '{skin_id}' is missing required emotion 'neutral'")

        # Validate emotion PNG lists are non-empty
        for emotion, files in emotions_raw.items():
            if not files:
                raise ValueError(f"Emotion '{emotion}' in skin '{skin_id}' has no files")

        emotions_list = list(emotions_raw.keys())

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

    store_provider = ""
    store_content_id = ""
    store_raw = data.get("deskmate_store")
    if isinstance(store_raw, dict):
        if store_raw.get("provider") is not None:
            store_provider = str(store_raw.get("provider"))
        if store_raw.get("content_id") is not None:
            store_content_id = str(store_raw.get("content_id"))

    return SkinInfo(
        id=skin_id,
        name=str(data.get("name", skin_id)),
        path=skin_path,
        author=str(data.get("author", "")) if data.get("author") is not None else "",
        version=str(data.get("version", "1.0")) if data.get("version") is not None else "1.0",
        description=str(data["description"]) if data.get("description") is not None else None,
        emotions=emotions_list,
        type=skin_type,
        live2d_config=live2d_config,
        bubble_placement=bubble_placement,
        input_placement=input_placement,
        bubble_theme=bubble_theme,
        idle_animations=idle_animations,
        source=source,
        format_version=int(data.get("format_version", 1)),
        store_provider=store_provider,
        store_content_id=store_content_id,
    )


def _default_user_skins_dir() -> Path:
    return Path(user_data_dir("deskmate")) / "skins"


class SkinLoader:
    def __init__(self, skins_dir: Path, user_skins_dir: Path | None = None):
        self._skins_dir = skins_dir
        self._user_skins_dir = user_skins_dir or _default_user_skins_dir()
        logger.info(f"User skins directory: {self._user_skins_dir}")

    def _scan_dir(self, directory: Path, source: str) -> list[SkinInfo]:
        skins: list[SkinInfo] = []
        if not directory.exists():
            return skins
        for entry in sorted(directory.iterdir()):
            if not entry.is_dir():
                continue
            if not (entry / "manifest.yaml").exists():
                continue
            skin_id = entry.name
            try:
                info = _load_manifest(skin_id, entry, source)
                skins.append(info)
                logger.info(f"Loaded skin: {info.name} ({skin_id}) [{source}]")
            except Exception as e:
                logger.warning(f"Failed to load skin at {entry}: {e}")
        return skins

    def list_skins(self) -> list[SkinInfo]:
        """Scan bundled and user skins directories, return all valid skins."""
        skins = self._scan_dir(self._skins_dir, "bundled")
        seen_ids = {s.id for s in skins}
        for skin in self._scan_dir(self._user_skins_dir, "community"):
            if skin.id in seen_ids:
                logger.warning(f"User skin '{skin.id}' shadows bundled skin, using user version")
                skins = [s for s in skins if s.id != skin.id]
            seen_ids.add(skin.id)
            skins.append(skin)
        return skins

    def installed_skin_ids(self) -> list[str]:
        return [skin.id for skin in self.list_skins() if skin.source == "community"]

    def installed_store_content_ids(self, provider: str) -> set[str]:
        return {
            skin.store_content_id
            for skin in self.list_skins()
            if skin.source == "community"
            and skin.store_provider == provider
            and skin.store_content_id
        }

    def load_skin(self, skin_id: str) -> SkinInfo:
        """Load a specific skin by ID. User skins take priority over bundled."""
        user_path = self._user_skins_dir / skin_id
        if user_path.is_dir() and (user_path / "manifest.yaml").exists():
            return _load_manifest(skin_id, user_path, "community")
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
        for d in (self._user_skins_dir, self._skins_dir):
            preview = d / skin_id / "preview.png"
            if preview.exists():
                return preview
        return None

    def install_skin(
        self, zip_path: Path, *, store_provider: str = "", store_content_id: str = ""
    ) -> str:
        with zipfile.ZipFile(zip_path) as archive:
            manifest_prefix = self._find_manifest_prefix(archive)
            manifest_name = f"{manifest_prefix}manifest.yaml"
            manifest_data = yaml.safe_load(archive.read(manifest_name).decode("utf-8"))
            if not isinstance(manifest_data, dict):
                raise ValueError("manifest.yaml in ZIP is not a YAML mapping")

            format_version = int(manifest_data.get("format_version", 1))
            if format_version > 2:
                raise ValueError(
                    f"This skin requires a newer DeskMate (format v{format_version}). Please update DeskMate."
                )

            if manifest_prefix:
                skin_id = manifest_prefix.rstrip("/")
            else:
                skin_id = zip_path.stem

            bundled_collision = any(
                skin.id == skin_id and skin.source == "bundled" for skin in self.list_skins()
            )
            if bundled_collision:
                skin_id = f"community-{skin_id}"

            target_dir = self._user_skins_dir / skin_id
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)

            for info in archive.infolist():
                name = info.filename
                if name.startswith("__MACOSX/") or name.endswith(".DS_Store"):
                    continue

                if manifest_prefix:
                    if not name.startswith(manifest_prefix):
                        continue
                    relative_name = name.removeprefix(manifest_prefix)
                else:
                    relative_name = name

                if not relative_name:
                    continue

                relative_path = Path(relative_name)
                if relative_path.is_absolute() or ".." in relative_path.parts:
                    raise ValueError(f"ZIP entry escapes skin directory: {name}")

                out_path = target_dir / relative_path
                if info.is_dir():
                    out_path.mkdir(parents=True, exist_ok=True)
                    continue

                out_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, out_path.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                logger.info(f"Extracted skin file: {out_path}")

        if store_provider and store_content_id:
            manifest_path = target_dir / "manifest.yaml"
            manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest_data, dict):
                raise ValueError("Installed manifest.yaml is not a YAML mapping")
            manifest_data["deskmate_store"] = {
                "provider": store_provider,
                "content_id": store_content_id,
            }
            manifest_path.write_text(
                yaml.safe_dump(manifest_data, sort_keys=False, allow_unicode=False),
                encoding="utf-8",
            )

        try:
            _load_manifest(skin_id, target_dir, "community")
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise
        logger.info(f"Installed skin: {skin_id} from {zip_path}")
        return skin_id

    def _find_manifest_prefix(self, archive: zipfile.ZipFile) -> str:
        names = archive.namelist()
        if "manifest.yaml" in names:
            return ""

        for name in names:
            if name.endswith("/manifest.yaml") and name.count("/") == 1:
                return name.split("/", 1)[0] + "/"

        raise ValueError("No manifest.yaml found in ZIP (checked root and one subfolder deep)")
