from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path


def make_executable(path: Path) -> None:
    current = path.stat().st_mode
    executable_bits = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    path.chmod(current | executable_bits)


def mark_trusted(path: Path) -> bool:
    gio = shutil.which("gio")
    if not gio:
        return False

    try:
        result = subprocess.run(
            [gio, "set", os.fspath(path), "metadata::trusted", "true"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    return result.returncode == 0


def is_executable(path: Path) -> bool:
    return os.access(path, os.X_OK)
