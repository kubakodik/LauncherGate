from __future__ import annotations

from enum import Enum
from pathlib import Path


class InputType(str, Enum):
    APPIMAGE = "appimage"
    DESKTOP = "desktop"
    ICON = "icon"
    JAR = "jar"
    PYTHON_SCRIPT = "python_script"
    SHELL_SCRIPT = "shell_script"
    UNSUPPORTED = "unsupported"


class ExecutionType(str, Enum):
    APPIMAGE = "appimage"
    JAR = "jar"
    PYTHON = "python"
    SHELL = "shell"
    UNKNOWN = "unknown"


def detect_input_type(path: Path) -> InputType:
    suffix = path.suffix.lower()
    if suffix == ".appimage":
        return InputType.APPIMAGE
    if suffix == ".jar":
        return InputType.JAR
    if suffix == ".desktop":
        return InputType.DESKTOP
    if suffix in (".png", ".svg", ".ico"):
        return InputType.ICON
    if suffix == ".py":
        return InputType.PYTHON_SCRIPT
    if suffix == ".sh":
        return InputType.SHELL_SCRIPT
    return InputType.UNSUPPORTED
