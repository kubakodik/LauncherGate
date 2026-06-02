from __future__ import annotations

import os
import hashlib
import shutil
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from core.desktop_paths import ensure_desktop_dir, quote_for_desktop_exec, safe_desktop_filename, unique_path
from core.file_types import ExecutionType, InputType, detect_input_type
from core.linux_ops import make_executable, mark_trusted

SYSTEM_FALLBACK_ICON = "application-x-executable"
ICON_CACHE_DIR_ENV = "LAUNCHER_GATE_ICON_CACHE_DIR"


@dataclass(frozen=True)
class LauncherResult:
    ok: bool
    message: str
    target: Path | None = None


@dataclass(frozen=True)
class DesktopMetadata:
    name: str | None = None
    comment: str | None = None
    categories: str | None = None
    terminal: str | None = None
    startup_notify: str | None = None
    icon: str | None = None
    execution_type: ExecutionType = ExecutionType.UNKNOWN


def process_drop(path: Path, icon_path: Path | None = None, metadata: DesktopMetadata | None = None) -> LauncherResult:
    try:
        source = path.expanduser().resolve()
        if not source.exists():
            return LauncherResult(False, "File does not exist.", None)
        if not source.is_file():
            return LauncherResult(False, "Drop a file, not a folder.", None)

        input_type = detect_input_type(source)
        if input_type == InputType.DESKTOP:
            return LauncherResult(False, ".desktop files are metadata sources. Drop a .sh, .py, .AppImage, or .jar next.", None)
        if input_type == InputType.APPIMAGE:
            return create_launcher_for_appimage(source, icon_path, metadata)
        if input_type == InputType.JAR:
            return create_launcher_for_jar(source, icon_path, metadata)
        if input_type == InputType.SHELL_SCRIPT:
            return create_launcher_for_shell_script(source, icon_path, metadata)
        if input_type == InputType.PYTHON_SCRIPT:
            return create_launcher_for_python_script(source, icon_path, metadata)

        return LauncherResult(False, "Unsupported type. V1 supports icons, .desktop, .sh, .py, .AppImage, and .jar.", None)
    except OSError as exc:
        return LauncherResult(False, f"Linux operation failed: {exc}", None)


def load_desktop_metadata(source: Path) -> DesktopMetadata:
    if not looks_like_desktop_entry(source):
        raise ValueError("File does not look like a valid .desktop launcher.")

    base_dir = source.parent
    content = source.read_text(encoding="utf-8", errors="replace")
    values = _parse_desktop_metadata(content)
    icon = values.get("Icon")
    if icon:
        values["Icon"] = _rewrite_icon_value(icon, base_dir)
    return DesktopMetadata(
        name=values.get("Name"),
        comment=values.get("Comment"),
        categories=values.get("Categories"),
        terminal=values.get("Terminal"),
        startup_notify=values.get("StartupNotify"),
        icon=values.get("Icon"),
        execution_type=classify_desktop_execution(source),
    )


def update_desktop_icon(source: Path, icon_path: Path | None) -> LauncherResult:
    try:
        source = source.expanduser().resolve()
        icon = _resolve_icon_path(icon_path)
        if icon is None:
            return LauncherResult(False, "Missing valid icon.", None)
        if not looks_like_desktop_entry(source):
            return LauncherResult(False, "File does not look like a valid .desktop launcher.", None)

        content = source.read_text(encoding="utf-8", errors="replace")
        source.write_text(rewrite_desktop_icon(content, icon), encoding="utf-8")
        make_executable(source)
        mark_trusted(source)
        return LauncherResult(True, "Icon updated.", source)
    except OSError as exc:
        return LauncherResult(False, f"Linux operation failed: {exc}", None)


def create_launcher_for_shell_script(
    script: Path,
    icon_path: Path | None = None,
    metadata: DesktopMetadata | None = None,
) -> LauncherResult:
    make_executable(script)
    return create_launcher_for_executable(
        executable=script,
        exec_line=quote_for_desktop_exec(script.expanduser().resolve()),
        icon_path=icon_path,
        metadata=metadata,
        default_name=_human_name(script.stem),
        default_terminal="false",
    )


def create_launcher_for_python_script(
    script: Path,
    icon_path: Path | None = None,
    metadata: DesktopMetadata | None = None,
) -> LauncherResult:
    python = _find_python_for_script(script)
    script = script.expanduser().resolve()
    exec_line = f"{quote_for_desktop_exec(python)} {quote_for_desktop_exec(script)}"
    return create_launcher_for_executable(
        executable=script,
        exec_line=exec_line,
        icon_path=icon_path,
        metadata=metadata,
        default_name=_human_name(script.stem),
        default_terminal="false",
    )


def create_launcher_for_appimage(
    appimage: Path,
    icon_path: Path | None = None,
    metadata: DesktopMetadata | None = None,
) -> LauncherResult:
    make_executable(appimage)
    appimage = appimage.expanduser().resolve()
    auto_icon = None if icon_path else extract_appimage_icon(appimage)
    return create_launcher_for_executable(
        executable=appimage,
        exec_line=os.fspath(appimage),
        icon_path=icon_path or auto_icon,
        metadata=metadata,
        default_name=_human_name(appimage.stem),
        default_terminal="false",
    )


def create_launcher_for_jar(
    jar: Path,
    icon_path: Path | None = None,
    metadata: DesktopMetadata | None = None,
) -> LauncherResult:
    jar = jar.expanduser().resolve()
    exec_line = f"java -jar {quote_for_desktop_exec(jar)}"
    return create_launcher_for_executable(
        executable=jar,
        exec_line=exec_line,
        icon_path=icon_path,
        metadata=metadata,
        default_name=_human_name(jar.stem),
        default_terminal="false",
    )


def create_launcher_for_executable(
    executable: Path,
    exec_line: str,
    icon_path: Path | None = None,
    metadata: DesktopMetadata | None = None,
    default_name: str | None = None,
    default_terminal: str = "false",
) -> LauncherResult:
    executable = executable.expanduser().resolve()
    desktop = ensure_desktop_dir()
    name = metadata.name if metadata and metadata.name else default_name or _human_name(executable.stem)
    launcher_name = safe_desktop_filename(f"{name}.desktop")
    target = unique_path(desktop, launcher_name)

    content = build_executable_launcher(executable, exec_line, icon_path, metadata, name, default_terminal)
    target.write_text(content, encoding="utf-8")
    make_executable(target)
    mark_trusted(target)

    return LauncherResult(True, "Launcher created.", target)


def build_shell_script_launcher(
    script: Path,
    icon_path: Path | None = None,
    metadata: DesktopMetadata | None = None,
) -> str:
    script = script.expanduser().resolve()
    return build_executable_launcher(
        executable=script,
        exec_line=quote_for_desktop_exec(script),
        icon_path=icon_path,
        metadata=metadata,
        name=metadata.name if metadata and metadata.name else _human_name(script.stem),
        default_terminal="false",
    )


def build_executable_launcher(
    executable: Path,
    exec_line: str,
    icon_path: Path | None = None,
    metadata: DesktopMetadata | None = None,
    name: str | None = None,
    default_terminal: str = "false",
) -> str:
    executable = executable.expanduser().resolve()
    metadata = metadata or DesktopMetadata()
    icon = _resolve_icon_path(icon_path) or metadata.icon or SYSTEM_FALLBACK_ICON
    terminal = metadata.terminal or default_terminal
    launcher_name = name or metadata.name or _human_name(executable.stem)

    lines = [
        "[Desktop Entry]",
        "Version=1.0",
        "Type=Application",
        f"Name={launcher_name}",
    ]
    if metadata.comment:
        lines.append(f"Comment={metadata.comment}")
    lines.extend(
        [
            f"Exec={exec_line}",
            f"Path={os.fspath(executable.parent)}",
            f"Terminal={terminal}",
            f"Icon={os.fspath(icon)}",
        ]
    )
    if metadata.categories:
        lines.append(f"Categories={metadata.categories}")
    if metadata.startup_notify:
        lines.append(f"StartupNotify={metadata.startup_notify}")
    lines.append("")
    return "\n".join(lines)


def _parse_desktop_metadata(content: str) -> dict[str, str]:
    wanted = {"Name", "Comment", "Categories", "Terminal", "StartupNotify", "Icon", "Exec"}
    values: dict[str, str] = {}
    in_desktop_entry = False

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_desktop_entry = line == "[Desktop Entry]"
            continue
        if not in_desktop_entry or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in wanted:
            values[key] = value
    return values


def classify_desktop_execution(source: Path) -> ExecutionType:
    if not looks_like_desktop_entry(source):
        return ExecutionType.UNKNOWN

    base_dir = source.expanduser().resolve().parent
    content = source.read_text(encoding="utf-8", errors="replace")
    values = _parse_desktop_metadata(content)
    return classify_exec_value(values.get("Exec", ""), base_dir)


def classify_exec_value(value: str, base_dir: Path) -> ExecutionType:
    try:
        parts = shlex.split(value)
    except ValueError:
        return ExecutionType.UNKNOWN
    if not parts:
        return ExecutionType.UNKNOWN

    command = _strip_wrapping_quotes(parts[0])
    command_path = _absolute_if_local_path(command, base_dir)
    command_name = os.fspath(command_path).lower()
    first_suffix = Path(command_name).suffix.lower()

    if first_suffix == ".appimage":
        return ExecutionType.APPIMAGE
    if first_suffix == ".jar":
        return ExecutionType.JAR
    if first_suffix == ".sh":
        return ExecutionType.SHELL
    if first_suffix == ".py":
        return ExecutionType.PYTHON

    if "python" in Path(command_name).name.lower() and len(parts) > 1:
        script_path = _strip_wrapping_quotes(parts[1])
        if Path(script_path).suffix.lower() == ".py":
            return ExecutionType.PYTHON

    if Path(command_name).name.lower() in {"sh", "bash", "dash", "zsh", "fish"} and len(parts) > 1:
        script_path = _strip_wrapping_quotes(parts[1])
        if Path(script_path).suffix.lower() == ".sh":
            return ExecutionType.SHELL

    if Path(command_name).name.lower() == "java" and "-jar" in parts:
        jar_index = parts.index("-jar") + 1
        if jar_index < len(parts) and Path(_strip_wrapping_quotes(parts[jar_index])).suffix.lower() == ".jar":
            return ExecutionType.JAR

    return ExecutionType.UNKNOWN


def extract_appimage_icon(appimage: Path) -> Path | None:
    appimage = appimage.expanduser().resolve()
    if not appimage.is_file():
        return None

    with tempfile.TemporaryDirectory(prefix="launcher-gate-appimage-") as temp:
        temp_dir = Path(temp)
        try:
            result = subprocess.run(
                [os.fspath(appimage), "--appimage-extract"],
                cwd=temp_dir,
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except (OSError, subprocess.SubprocessError):
            return None

        root = temp_dir / "squashfs-root"
        if result.returncode != 0 or not root.is_dir():
            return None

        icon = _find_extracted_appimage_icon(root)
        if icon is None:
            return None
        return _cache_extracted_icon(appimage, icon)


def _find_extracted_appimage_icon(root: Path) -> Path | None:
    desktop_icon = _read_extracted_desktop_icon(root)
    if desktop_icon:
        icon = _find_icon_for_desktop_value(root, desktop_icon)
        if icon is not None:
            return icon

    dir_icon = root / ".DirIcon"
    if dir_icon.is_file() and _is_supported_icon_file(dir_icon):
        return dir_icon.resolve()

    return _best_icon_candidate(root.rglob("*"))


def _read_extracted_desktop_icon(root: Path) -> str | None:
    for desktop in sorted(root.rglob("*.desktop")):
        try:
            values = _parse_desktop_metadata(desktop.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        icon = values.get("Icon")
        if icon:
            return icon
    return None


def _find_icon_for_desktop_value(root: Path, value: str) -> Path | None:
    icon = _strip_wrapping_quotes(value.strip())
    if not icon:
        return None

    if _looks_like_relative_file_path(icon) or Path(icon).is_absolute():
        candidate = root / icon.lstrip("/")
        if candidate.is_file() and _is_supported_icon_file(candidate):
            return candidate.resolve()

    return _best_icon_candidate(
        candidate for candidate in root.rglob("*") if candidate.is_file() and candidate.stem == Path(icon).stem
    )


def _best_icon_candidate(candidates) -> Path | None:
    supported = [candidate.resolve() for candidate in candidates if candidate.is_file() and _is_supported_icon_file(candidate)]
    if not supported:
        return None

    def priority(path: Path) -> tuple[int, int, str]:
        suffix_rank = {".svg": 3, ".png": 2, ".ico": 1}.get(path.suffix.lower(), 0)
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        return suffix_rank, size, os.fspath(path)

    return max(supported, key=priority)


def _cache_extracted_icon(appimage: Path, icon: Path) -> Path | None:
    try:
        cache_dir = _icon_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(os.fspath(appimage).encode("utf-8")).hexdigest()[:12]
        target = cache_dir / safe_desktop_filename(f"{appimage.stem}-{digest}{icon.suffix.lower()}")
        shutil.copy2(icon, target)
        return target.resolve()
    except OSError:
        return None


def _icon_cache_dir() -> Path:
    configured = os.environ.get(ICON_CACHE_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser()
    data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    return base / "launcher-gate" / "icons"


def _is_supported_icon_file(path: Path) -> bool:
    return path.suffix.lower() in {".png", ".svg", ".ico"}


def rewrite_desktop_paths(content: str, base_dir: Path, icon_path: Path | None = None) -> str:
    base_dir = base_dir.expanduser().resolve()
    override_icon = _resolve_icon_path(icon_path)
    rewritten = []
    has_icon = False

    for line in content.splitlines():
        if line.startswith("Exec="):
            rewritten.append(f"Exec={_rewrite_exec(line.removeprefix('Exec='), base_dir)}")
        elif line.startswith("Path="):
            rewritten.append(f"Path={_rewrite_path_value(line.removeprefix('Path='), base_dir)}")
        elif line.startswith("Icon="):
            has_icon = True
            icon = os.fspath(override_icon) if override_icon else _rewrite_icon_value(line.removeprefix("Icon="), base_dir)
            rewritten.append(f"Icon={icon}")
        else:
            rewritten.append(line)

    if not has_icon:
        icon = os.fspath(override_icon) if override_icon else SYSTEM_FALLBACK_ICON
        rewritten.append(f"Icon={icon}")

    suffix = "\n" if content.endswith("\n") else ""
    return "\n".join(rewritten) + suffix


def rewrite_desktop_icon(content: str, icon_path: Path) -> str:
    icon = os.fspath(icon_path.expanduser().resolve())
    rewritten = []
    has_icon = False

    for line in content.splitlines():
        if line.startswith("Icon="):
            has_icon = True
            rewritten.append(f"Icon={icon}")
        else:
            rewritten.append(line)

    if not has_icon:
        rewritten.append(f"Icon={icon}")

    suffix = "\n" if content.endswith("\n") else ""
    return "\n".join(rewritten) + suffix


def _resolve_icon_path(icon_path: Path | None) -> Path | None:
    if icon_path is None:
        return None
    candidate = icon_path.expanduser().resolve()
    if candidate.is_file() and detect_input_type(candidate) == InputType.ICON:
        return candidate
    return None


def _find_python_for_script(script: Path) -> Path:
    start = script.expanduser().resolve().parent
    for directory in (start, *start.parents):
        for environment_dir in (".venv", "venv"):
            candidate = directory / environment_dir / "bin" / "python"
            if candidate.is_file():
                return candidate
    return Path(sys.executable).resolve()


def _rewrite_exec(value: str, base_dir: Path) -> str:
    try:
        parts = shlex.split(value)
    except ValueError:
        return value
    if not parts:
        return value

    command = parts[0]
    rewritten_command = _absolute_if_local_path(command, base_dir)
    parts[0] = _quote_desktop_arg(os.fspath(rewritten_command)) if rewritten_command != command else command
    return " ".join(_quote_desktop_arg(part) if index else part for index, part in enumerate(parts))


def _rewrite_path_value(value: str, base_dir: Path) -> str:
    path = _strip_wrapping_quotes(value.strip())
    if not path:
        return value
    return os.fspath(_absolute_if_relative_path(path, base_dir))


def _rewrite_icon_value(value: str, base_dir: Path) -> str:
    icon = _strip_wrapping_quotes(value.strip())
    if not icon:
        return SYSTEM_FALLBACK_ICON

    if _looks_like_relative_file_path(icon) or Path(icon).is_absolute():
        absolute_icon = _absolute_if_relative_path(icon, base_dir)
        if absolute_icon.is_file():
            return os.fspath(absolute_icon)
        return SYSTEM_FALLBACK_ICON

    candidate = base_dir / icon
    if candidate.is_file():
        return os.fspath(candidate.resolve())

    return icon


def _absolute_if_local_path(value: str, base_dir: Path) -> Path | str:
    if _looks_like_relative_file_path(value) or Path(value).is_absolute():
        return _absolute_if_relative_path(value, base_dir)
    candidate = base_dir / value
    if candidate.exists():
        return candidate.resolve()
    return value


def _absolute_if_relative_path(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _looks_like_relative_file_path(value: str) -> bool:
    return value.startswith(("./", "../")) or "/" in value


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _quote_desktop_arg(value: str) -> str:
    if not value or any(char.isspace() for char in value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def looks_like_desktop_entry(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            head = handle.read(4096)
    except OSError:
        return False

    return "[Desktop Entry]" in head and "Type=" in head


def _human_name(stem: str) -> str:
    cleaned = stem.replace("_", " ").replace("-", " ").strip()
    if not cleaned:
        return "Launcher"
    return " ".join(part[:1].upper() + part[1:] for part in cleaned.split())
