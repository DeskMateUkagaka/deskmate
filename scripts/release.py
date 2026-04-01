#!/usr/bin/env python3
"""Build DeskMate release artifacts with the official PySide6 deploy tool.

This script is intentionally a single entry point with modular internals:
- shared release metadata, staging, docs, and archive logic live here once
- target-specific checks and artifact formats are isolated in small functions

Qt for Python's recommended desktop deployment tool is `pyside6-deploy`, which
wraps Nuitka. This script orchestrates it rather than replacing it.
"""

import configparser
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
MAIN_FILE = APP_DIR / "main.py"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "dist" / "release"
DOC_FILES = [
    ROOT_DIR / "LICENSE",
    ROOT_DIR / "NOTICE",
    ROOT_DIR / "THIRD_PARTY_NOTICES.md",
    ROOT_DIR / "README.md",
]
DATA_DIRS = [
    APP_DIR / "icons",
    APP_DIR / "skins",
]
PYSIDE_MODULES = [
    "Core",
    "Gui",
    "Network",
    "WebChannel",
    "WebEngineCore",
    "WebEngineWidgets",
    "Widgets",
]

app = typer.Typer(
    add_completion=False, help="Build a DeskMate desktop release.", pretty_exceptions_enable=False
)


class ReleaseError(RuntimeError):
    """Raised when release packaging cannot proceed."""


@dataclass(frozen=True)
class TargetInfo:
    key: str
    deploy_name: str
    archive_format: str
    archive_suffix: str
    executable_suffix: str


@dataclass(frozen=True)
class ReleaseContext:
    version: str
    target: TargetInfo
    arch: str
    output_dir: Path
    work_dir: Path
    stage_dir: Path
    spec_file: Path
    artifact_base: str
    icon_path: Path


TARGETS = {
    "linux": TargetInfo(
        key="linux",
        deploy_name="linux",
        archive_format="gztar",
        archive_suffix=".tar.gz",
        executable_suffix=".dist",
    ),
    "windows": TargetInfo(
        key="windows",
        deploy_name="windows",
        archive_format="zip",
        archive_suffix=".zip",
        executable_suffix=".dist",
    ),
    "macos": TargetInfo(
        key="macos",
        deploy_name="macos",
        archive_format="zip",
        archive_suffix=".zip",
        executable_suffix=".app",
    ),
}


def log(message: str) -> None:
    print(f"[release] {message}")


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    rendered = " ".join(str(part) for part in command)
    log(f"Running: {rendered}")
    subprocess.run(command, cwd=cwd or ROOT_DIR, env=env, check=True)


def write_ini(path: Path, parser: configparser.ConfigParser) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        parser.write(handle)
    log(f"Wrote file: {path}")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    log(f"Wrote file: {path}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_target() -> TargetInfo:
    if sys.platform.startswith("linux"):
        return TARGETS["linux"]
    if sys.platform == "win32":
        return TARGETS["windows"]
    if sys.platform == "darwin":
        return TARGETS["macos"]
    raise ReleaseError(f"Unsupported host platform: {sys.platform}")


def normalize_arch() -> str:
    machine = platform.machine().lower()
    aliases = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "arm64": "aarch64",
    }
    return aliases.get(machine, machine)


def require_existing(path: Path) -> None:
    if not path.exists():
        raise ReleaseError(f"Required path is missing: {path}")


def require_command(name: str, *, hint: str | None = None) -> None:
    if shutil.which(name):
        return

    message = f"Required command not found on PATH: {name}"
    if hint:
        message += f" ({hint})"
    raise ReleaseError(message)


def ensure_tooling(target: TargetInfo) -> None:
    require_command("pyside6-deploy", hint="activate the PySide6 build environment first")

    if target.key == "linux":
        require_command("readelf")
    elif target.key == "windows":
        require_command("dumpbin", hint="run from an MSVC developer shell")
    elif target.key == "macos":
        require_command("dyld_info")

    pip_command = [sys.executable, "-m", "pip", "--version"]
    try:
        subprocess.run(pip_command, cwd=ROOT_DIR, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise ReleaseError(
            "The active Python environment does not have a working pip, but "
            "pyside6-deploy requires it to manage Nuitka and related build dependencies. "
            "Install pip into the active environment first."
        ) from exc


def ensure_native_target(requested: str, current: TargetInfo) -> TargetInfo:
    if requested == "current":
        return current

    target = TARGETS[requested]
    if target.key != current.key:
        raise ReleaseError(
            "Cross-building is not supported by this script. "
            f"Requested target '{target.key}' from host '{current.key}'. "
            "Run the same script on the native target OS instead."
        )
    return target


def resolve_icon(target: TargetInfo, explicit_icon: str | None) -> Path:
    if explicit_icon:
        icon_path = Path(explicit_icon).expanduser().resolve()
        require_existing(icon_path)
        return icon_path

    if target.key == "linux":
        icon_path = APP_DIR / "icons" / "icon.png"
    elif target.key == "windows":
        icon_path = APP_DIR / "icons" / "icon.ico"
    else:
        icon_path = APP_DIR / "icons" / "icon.icns"

    if icon_path.exists():
        return icon_path

    raise ReleaseError(
        f"No default icon found for target '{target.key}' at {icon_path}. Provide one with --icon."
    )


def build_context(
    *,
    version: str,
    output_dir: str,
    icon: str | None,
    target: TargetInfo,
) -> ReleaseContext:
    arch = normalize_arch()
    artifact_base = f"deskmate-{version}-{target.key}-{arch}"
    resolved_output_dir = Path(output_dir).expanduser().resolve()
    work_dir = resolved_output_dir / ".work" / artifact_base
    stage_dir = resolved_output_dir / artifact_base
    spec_file = work_dir / "pysidedeploy.spec"
    icon_path = resolve_icon(target, icon)
    return ReleaseContext(
        version=version,
        target=target,
        arch=arch,
        output_dir=resolved_output_dir,
        work_dir=work_dir,
        stage_dir=stage_dir,
        spec_file=spec_file,
        artifact_base=artifact_base,
        icon_path=icon_path,
    )


def clean_paths(context: ReleaseContext) -> None:
    for path in [
        context.work_dir,
        context.stage_dir,
        context.output_dir / f"{context.artifact_base}{context.target.archive_suffix}",
    ]:
        if path.is_dir():
            shutil.rmtree(path)
            log(f"Removed directory: {path}")
        elif path.exists():
            path.unlink()
            log(f"Removed file: {path}")


def nuitka_extra_args() -> str:
    args = [
        "--quiet",
        "--noinclude-qt-translations",
        f"--include-data-dir={APP_DIR / 'skins'}=./skins",
        f"--include-data-dir={APP_DIR / 'icons'}=./icons",
    ]
    return " ".join(str(part) for part in args)


def write_spec_file(context: ReleaseContext) -> None:
    parser = configparser.ConfigParser()
    parser["app"] = {
        "title": context.artifact_base,
        "project_dir": str(APP_DIR),
        "input_file": str(MAIN_FILE),
        "exec_directory": str(context.stage_dir),
        "project_file": "",
        "icon": str(context.icon_path),
    }
    parser["python"] = {
        "python_path": sys.executable,
        "packages": "Nuitka==2.7.11",
        "android_packages": "buildozer==1.5.0,cython==0.29.33",
    }
    parser["qt"] = {
        "qml_files": "",
        "excluded_qml_plugins": "",
        "modules": ",".join(PYSIDE_MODULES),
        "plugins": "platformthemes",
    }
    parser["android"] = {
        "wheel_pyside": "",
        "wheel_shiboken": "",
        "plugins": "",
    }
    parser["nuitka"] = {
        "macos.permissions": "",
        "mode": "standalone",
        "extra_args": nuitka_extra_args(),
    }
    parser["buildozer"] = {
        "mode": "debug",
        "recipe_dir": "",
        "jars_dir": "",
        "ndk_path": "",
        "sdk_path": "",
        "local_libs": "",
        "arch": "",
    }
    write_ini(context.spec_file, parser)


def run_deploy(context: ReleaseContext) -> Path:
    run(["pyside6-deploy", "-c", str(context.spec_file), "-f"])
    bundle_path = context.stage_dir / f"{context.artifact_base}{context.target.executable_suffix}"
    require_existing(bundle_path)
    return bundle_path


def docs_destination(bundle_path: Path, target: TargetInfo) -> Path:
    if target.key == "macos":
        return bundle_path / "Contents" / "Resources" / "docs"
    return bundle_path / "docs"


def bundle_docs(bundle_path: Path, target: TargetInfo) -> None:
    destination = docs_destination(bundle_path, target)
    destination.mkdir(parents=True, exist_ok=True)
    log(f"Created directory: {destination}")
    for source in DOC_FILES:
        require_existing(source)
        target_path = destination / source.name
        shutil.copy2(source, target_path)
        log(f"Wrote file: {target_path}")


def archive_bundle(bundle_path: Path, context: ReleaseContext) -> Path:
    archive_base = context.output_dir / context.artifact_base
    archive_path = Path(
        shutil.make_archive(
            str(archive_base),
            context.target.archive_format,
            root_dir=bundle_path.parent,
            base_dir=bundle_path.name,
        )
    )
    log(f"Wrote file: {archive_path}")
    return archive_path


def write_manifest(bundle_path: Path, archive_path: Path, context: ReleaseContext) -> Path:
    manifest_path = context.output_dir / f"{context.artifact_base}-manifest.json"
    manifest = {
        "name": "DeskMate",
        "version": context.version,
        "target": context.target.key,
        "architecture": context.arch,
        "bundle_path": str(bundle_path),
        "archive_path": str(archive_path),
        "archive_sha256": sha256_file(archive_path),
        "spec_file": str(context.spec_file),
        "tool": "pyside6-deploy",
        "packaging_backend": "Nuitka via pyside6-deploy",
        "host_python": sys.executable,
    }
    write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest_path


def verify_inputs() -> None:
    require_existing(MAIN_FILE)
    for path in DOC_FILES + DATA_DIRS:
        require_existing(path)


@app.command()
def main(
    version: Annotated[
        str,
        typer.Option(help="Release version label, e.g. 0.1.0"),
    ],
    target_name: Annotated[
        str,
        typer.Option(
            "--target",
            help="Build target. Cross-building is intentionally rejected.",
            case_sensitive=False,
        ),
    ] = "current",
    output_dir: Annotated[
        str,
        typer.Option(help="Directory where release artifacts are written"),
    ] = str(DEFAULT_OUTPUT_DIR),
    icon: Annotated[
        str | None,
        typer.Option(help="Override the platform-specific application icon path"),
    ] = None,
    keep_work_dir: Annotated[
        bool,
        typer.Option(help="Keep the generated work directory and spec file after packaging"),
    ] = False,
) -> None:
    current_target = detect_target()
    target_name = target_name.lower()
    if target_name not in {"current", "linux", "windows", "macos"}:
        raise ReleaseError(f"Unsupported target '{target_name}'")

    target = ensure_native_target(target_name, current_target)
    verify_inputs()
    ensure_tooling(target)

    context = build_context(version=version, output_dir=output_dir, icon=icon, target=target)
    clean_paths(context)
    context.output_dir.mkdir(parents=True, exist_ok=True)
    log(f"Created directory: {context.output_dir}")
    context.work_dir.mkdir(parents=True, exist_ok=True)
    log(f"Created directory: {context.work_dir}")
    context.stage_dir.mkdir(parents=True, exist_ok=True)
    log(f"Created directory: {context.stage_dir}")

    write_spec_file(context)
    bundle_path = run_deploy(context)
    bundle_docs(bundle_path, target)
    archive_path = archive_bundle(bundle_path, context)
    manifest_path = write_manifest(bundle_path, archive_path, context)

    if not keep_work_dir and context.work_dir.exists():
        shutil.rmtree(context.work_dir)
        log(f"Removed directory: {context.work_dir}")

    log(f"Bundle ready: {bundle_path}")
    log(f"Archive ready: {archive_path}")
    log(f"Manifest ready: {manifest_path}")


if __name__ == "__main__":
    try:
        app()
    except ReleaseError as exc:
        log(f"Error: {exc}")
        raise SystemExit(1)
