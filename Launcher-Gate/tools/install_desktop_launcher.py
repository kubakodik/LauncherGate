from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from core.desktop_paths import ensure_desktop_dir, quote_for_desktop_exec
from core.linux_ops import make_executable, mark_trusted


APP_ID = "linux-dnd-launcher-gate"
APP_NAME = "Launcher Gate"
LAUNCHER_FILENAME = f"{APP_ID}.desktop"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_desktop_entry(root: Path) -> str:
    python_bin = root / ".venv" / "bin" / "python"
    main_py = root / "main.py"
    icon = root / "icons" / "launcher-gate.svg"

    return "\n".join(
        [
            "[Desktop Entry]",
            "Version=1.0",
            "Type=Application",
            f"Name={APP_NAME}",
            "Comment=Drag and drop Linux launcher builder",
            f"Exec={quote_for_desktop_exec(python_bin)} {quote_for_desktop_exec(main_py)}",
            f"Path={os.fspath(root)}",
            f"Icon={os.fspath(icon)}",
            "Terminal=false",
            "StartupNotify=true",
            "Categories=Utility;",
            "",
        ]
    )


def validate_runtime(root: Path) -> None:
    required = [
        root / ".venv" / "bin" / "python",
        root / "main.py",
        root / "icons" / "launcher-gate.svg",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Missing files for desktop launcher:\n{formatted}")


def write_project_launcher(root: Path) -> Path:
    launcher_dir = root / "launchers"
    launcher_dir.mkdir(parents=True, exist_ok=True)
    launcher_path = launcher_dir / LAUNCHER_FILENAME
    launcher_path.write_text(build_desktop_entry(root), encoding="utf-8")
    make_executable(launcher_path)
    return launcher_path


def install_to_desktop(project_launcher: Path) -> Path:
    desktop = ensure_desktop_dir()
    target = desktop / LAUNCHER_FILENAME
    shutil.copy2(project_launcher, target)
    make_executable(target)
    mark_trusted(target)
    return target


def validate_desktop_file(path: Path) -> tuple[bool, str]:
    validator = shutil.which("desktop-file-validate")
    if not validator:
        return True, "desktop-file-validate is not available"

    result = subprocess.run(
        [validator, os.fspath(path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output


def main() -> int:
    root = project_root()
    validate_runtime(root)

    project_launcher = write_project_launcher(root)
    desktop_launcher = install_to_desktop(project_launcher)

    valid, validation_output = validate_desktop_file(desktop_launcher)
    print(f"Project launcher: {project_launcher}")
    print(f"Desktop launcher: {desktop_launcher}")
    print(f"Executable: yes")
    print(f"Trusted flag attempted: yes")

    if not valid:
        print(validation_output)
        return 1

    if validation_output:
        print(validation_output)
    print("Launcher Gate desktop launcher installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
