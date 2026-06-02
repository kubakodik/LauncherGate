from pathlib import Path

from core.file_types import ExecutionType, InputType, detect_input_type
from core.launcher_builder import (
    SYSTEM_FALLBACK_ICON,
    DesktopMetadata,
    build_shell_script_launcher,
    classify_desktop_execution,
    classify_exec_value,
    load_desktop_metadata,
    update_desktop_icon,
)


def test_detect_input_type() -> None:
    assert detect_input_type(Path("app.desktop")) == InputType.DESKTOP
    assert detect_input_type(Path("app.png")) == InputType.ICON
    assert detect_input_type(Path("app.svg")) == InputType.ICON
    assert detect_input_type(Path("app.ico")) == InputType.ICON
    assert detect_input_type(Path("run.py")) == InputType.PYTHON_SCRIPT
    assert detect_input_type(Path("run.sh")) == InputType.SHELL_SCRIPT
    assert detect_input_type(Path("Obsidian.AppImage")) == InputType.APPIMAGE
    assert detect_input_type(Path("obsidian.appimage")) == InputType.APPIMAGE
    assert detect_input_type(Path("viewer.jar")) == InputType.JAR
    assert detect_input_type(Path("notes.txt")) == InputType.UNSUPPORTED


def test_build_shell_script_launcher_contains_required_fields(tmp_path) -> None:
    script = tmp_path / "my_app.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    icon = tmp_path / "my_app.png"
    icon.write_text("icon\n", encoding="utf-8")

    content = build_shell_script_launcher(script, icon)

    assert "[Desktop Entry]" in content
    assert "Version=1.0" in content
    assert "Type=Application" in content
    assert "Name=My App" in content
    assert f'Exec="{script.resolve()}"' in content
    assert f"Path={script.parent.resolve()}" in content
    assert "Terminal=false" in content
    assert f"Icon={icon.resolve()}" in content


def test_build_shell_script_launcher_uses_system_fallback_icon(tmp_path) -> None:
    script = tmp_path / "my_app.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")

    content = build_shell_script_launcher(script)

    assert f"Icon={SYSTEM_FALLBACK_ICON}" in content


def test_build_shell_script_launcher_does_not_guess_same_basename_icon(tmp_path) -> None:
    script = tmp_path / "tool.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    icon = tmp_path / "tool.svg"
    icon.write_text("icon\n", encoding="utf-8")

    content = build_shell_script_launcher(script)

    assert f"Icon={SYSTEM_FALLBACK_ICON}" in content
    assert f"Icon={icon.resolve()}" not in content


def test_build_shell_script_launcher_uses_desktop_metadata(tmp_path) -> None:
    script = tmp_path / "tool.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    metadata = DesktopMetadata(
        name="Dictovani",
        comment="Speech launcher",
        categories="Utility;",
        terminal="true",
        startup_notify="false",
        icon="audio-input-microphone",
    )

    content = build_shell_script_launcher(script, metadata=metadata)

    assert "Name=Dictovani" in content
    assert "Comment=Speech launcher" in content
    assert "Terminal=true" in content
    assert "Icon=audio-input-microphone" in content
    assert "Categories=Utility;" in content
    assert "StartupNotify=false" in content


def test_load_desktop_metadata_ignores_exec_and_path(tmp_path) -> None:
    icon = tmp_path / "meta.png"
    icon.write_text("icon\n", encoding="utf-8")
    launcher = tmp_path / "meta.desktop"
    launcher.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Metadata Name",
                "Comment=Metadata comment",
                "Exec=./broken.sh",
                "Path=./broken",
                "Icon=meta.png",
                "Terminal=true",
                "Categories=Utility;",
                "StartupNotify=false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    metadata = load_desktop_metadata(launcher)

    assert metadata.name == "Metadata Name"
    assert metadata.comment == "Metadata comment"
    assert metadata.icon == str(icon.resolve())
    assert metadata.terminal == "true"
    assert metadata.categories == "Utility;"
    assert metadata.startup_notify == "false"
    assert metadata.execution_type == ExecutionType.SHELL
    assert not hasattr(metadata, "exec")
    assert not hasattr(metadata, "path")


def test_update_desktop_icon_rewrites_only_icon(tmp_path) -> None:
    icon = tmp_path / "new.png"
    icon.write_text("icon\n", encoding="utf-8")
    launcher = tmp_path / "app.desktop"
    launcher.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Original",
                "Exec=./keep-this.sh",
                "Path=./keep-this",
                "Icon=old-icon",
                "Terminal=false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = update_desktop_icon(launcher, icon)

    assert result.ok
    content = launcher.read_text(encoding="utf-8")
    assert f"Icon={icon.resolve()}" in content
    assert "Exec=./keep-this.sh" in content
    assert "Path=./keep-this" in content
    assert "Name=Original" in content


def test_classifies_desktop_exec_types(tmp_path) -> None:
    appimage = tmp_path / "Obsidian.AppImage"
    jar = tmp_path / "viewer.jar"
    shell = tmp_path / "run.sh"
    python_script = tmp_path / "run.py"
    for source in (appimage, jar, shell, python_script):
        source.write_text("", encoding="utf-8")

    assert classify_exec_value("./Obsidian.AppImage", tmp_path) == ExecutionType.APPIMAGE
    assert classify_exec_value("./viewer.jar", tmp_path) == ExecutionType.JAR
    assert classify_exec_value(f'java -jar "{jar}"', tmp_path) == ExecutionType.JAR
    assert classify_exec_value("./run.sh", tmp_path) == ExecutionType.SHELL
    assert classify_exec_value(f'"/usr/bin/python3" "{python_script}"', tmp_path) == ExecutionType.PYTHON
    assert classify_exec_value("unknown-command --flag", tmp_path) == ExecutionType.UNKNOWN


def test_classifies_desktop_launcher_pointing_to_appimage(tmp_path) -> None:
    appimage = tmp_path / "Tool.AppImage"
    appimage.write_text("binary\n", encoding="utf-8")
    launcher = tmp_path / "tool.desktop"
    launcher.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Tool",
                "Exec=./Tool.AppImage",
                "",
            ]
        ),
        encoding="utf-8",
    )

    metadata = load_desktop_metadata(launcher)

    assert classify_desktop_execution(launcher) == ExecutionType.APPIMAGE
    assert metadata.execution_type == ExecutionType.APPIMAGE


def test_classifies_desktop_launcher_pointing_to_jar(tmp_path) -> None:
    jar = tmp_path / "Viewer.jar"
    jar.write_text("binary\n", encoding="utf-8")
    launcher = tmp_path / "viewer.desktop"
    launcher.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Viewer",
                f'Exec=java -jar "{jar}"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    metadata = load_desktop_metadata(launcher)

    assert classify_desktop_execution(launcher) == ExecutionType.JAR
    assert metadata.execution_type == ExecutionType.JAR
