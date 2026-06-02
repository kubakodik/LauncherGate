from __future__ import annotations

import os
import subprocess
from pathlib import Path

DESKTOP_DIR_ENV = "LAUNCHER_GATE_DESKTOP_DIR"


def get_desktop_dir() -> Path:
    configured = os.environ.get(DESKTOP_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser()

    try:
        result = subprocess.run(
            ["xdg-user-dir", "DESKTOP"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        candidate = result.stdout.strip()
        if result.returncode == 0 and candidate:
            return Path(candidate).expanduser()
    except (OSError, subprocess.SubprocessError):
        pass

    home = Path.home()
    for name in ("Desktop", "Plocha"):
        candidate = home / name
        if candidate.exists():
            return candidate
    return home / "Desktop"


def ensure_desktop_dir() -> Path:
    desktop = get_desktop_dir()
    desktop.mkdir(parents=True, exist_ok=True)
    return desktop


def unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        next_candidate = directory / f"{stem}-{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        index += 1


def quote_for_desktop_exec(path: Path) -> str:
    raw = os.fspath(path)
    escaped = raw.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def safe_desktop_filename(name: str) -> str:
    keep = []
    for char in name.strip():
        if char.isalnum() or char in (" ", "-", "_", "."):
            keep.append(char)
        else:
            keep.append("-")
    cleaned = "".join(keep).strip(" .")
    return cleaned or "Launcher.desktop"
