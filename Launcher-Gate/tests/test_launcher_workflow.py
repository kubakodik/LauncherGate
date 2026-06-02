from __future__ import annotations

import os

from core.desktop_paths import DESKTOP_DIR_ENV
from core.launcher_builder import ICON_CACHE_DIR_ENV, SYSTEM_FALLBACK_ICON, load_desktop_metadata, process_drop


def test_process_shell_script_creates_desktop_launcher(tmp_path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(desktop))

    script = tmp_path / "run_demo.sh"
    script.write_text("#!/bin/sh\necho demo\n", encoding="utf-8")
    icon = tmp_path / "run_demo.ico"
    icon.write_text("icon\n", encoding="utf-8")

    result = process_drop(script, icon)

    assert result.ok
    assert result.target == desktop / "Run Demo.desktop"
    assert result.target.exists()
    assert os.access(script, os.X_OK)
    assert os.access(result.target, os.X_OK)

    launcher = result.target.read_text(encoding="utf-8")
    assert "Name=Run Demo" in launcher
    assert f'Exec="{script.resolve()}"' in launcher
    assert f"Path={tmp_path}" in launcher
    assert "Terminal=false" in launcher
    assert f"Icon={icon.resolve()}" in launcher


def test_process_shell_script_uses_system_fallback_without_pending_icon(tmp_path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(desktop))

    script = tmp_path / "run_demo.sh"
    script.write_text("#!/bin/sh\necho demo\n", encoding="utf-8")

    result = process_drop(script)

    assert result.ok
    launcher = result.target.read_text(encoding="utf-8")
    assert "Terminal=false" in launcher
    assert f"Icon={SYSTEM_FALLBACK_ICON}" in launcher


def test_process_python_script_creates_desktop_launcher(tmp_path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(desktop))

    script = tmp_path / "run_demo.py"
    script.write_text("print('demo')\n", encoding="utf-8")

    result = process_drop(script)

    assert result.ok
    assert result.target == desktop / "Run Demo.desktop"
    launcher = result.target.read_text(encoding="utf-8")
    assert f'"{script.resolve()}"' in launcher
    assert f"Path={tmp_path}" in launcher
    assert "Terminal=false" in launcher
    assert f"Icon={SYSTEM_FALLBACK_ICON}" in launcher
    assert os.access(result.target, os.X_OK)


def test_process_python_script_uses_local_venv_python(tmp_path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(desktop))

    python = tmp_path / "venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    script = tmp_path / "run_demo.py"
    script.write_text("print('demo')\n", encoding="utf-8")

    result = process_drop(script)

    assert result.ok
    launcher = result.target.read_text(encoding="utf-8")
    assert f'Exec="{python.resolve()}" "{script.resolve()}"' in launcher


def test_process_jar_creates_desktop_launcher(tmp_path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(desktop))

    jar = tmp_path / "Viewer.jar"
    jar.write_text("binary\n", encoding="utf-8")

    result = process_drop(jar)

    assert result.ok
    assert result.target == desktop / "Viewer.desktop"
    launcher = result.target.read_text(encoding="utf-8")
    assert f'Exec=java -jar "{jar.resolve()}"' in launcher
    assert f"Path={tmp_path}" in launcher
    assert "Terminal=false" in launcher
    assert f"Icon={SYSTEM_FALLBACK_ICON}" in launcher


def test_process_jar_uses_pending_icon_and_metadata(tmp_path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(desktop))

    icon = tmp_path / "viewer.png"
    icon.write_text("icon\n", encoding="utf-8")
    jar = tmp_path / "vendor-viewer.jar"
    jar.write_text("binary\n", encoding="utf-8")
    metadata = load_desktop_metadata(
        _write_desktop(
            tmp_path / "metadata.desktop",
            [
                "Name=Vendor Viewer",
                "Comment=Portable Java app",
                "Exec=java -jar old.jar",
                "Icon=old-icon",
                "Terminal=true",
            ],
        )
    )

    result = process_drop(jar, icon, metadata)

    assert result.ok
    launcher = result.target.read_text(encoding="utf-8")
    assert "Name=Vendor Viewer" in launcher
    assert "Comment=Portable Java app" in launcher
    assert f'Exec=java -jar "{jar.resolve()}"' in launcher
    assert f"Icon={icon.resolve()}" in launcher
    assert "Terminal=true" in launcher
    assert "old.jar" not in launcher


def test_process_appimage_creates_desktop_launcher(tmp_path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(desktop))

    appimage = tmp_path / "Obsidian.AppImage"
    appimage.write_text("binary\n", encoding="utf-8")

    result = process_drop(appimage)

    assert result.ok
    assert result.target == desktop / "Obsidian.desktop"
    assert os.access(appimage, os.X_OK)
    launcher = result.target.read_text(encoding="utf-8")
    assert f"Exec={appimage.resolve()}" in launcher
    assert "--no-sandbox" not in launcher
    assert f"Path={tmp_path}" in launcher
    assert "Terminal=false" in launcher
    assert f"Icon={SYSTEM_FALLBACK_ICON}" in launcher


def test_process_appimage_extracts_embedded_icon_without_pending_icon(tmp_path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    icon_cache = tmp_path / "icon-cache"
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(desktop))
    monkeypatch.setenv(ICON_CACHE_DIR_ENV, os.fspath(icon_cache))

    appimage = tmp_path / "Obsidian.AppImage"
    appimage.write_text("binary\n", encoding="utf-8")

    def fake_extract(command, *args, **kwargs):
        if "--appimage-extract" not in command:
            class OtherResult:
                returncode = 1

            return OtherResult()

        cwd = kwargs["cwd"]
        check = kwargs["check"]
        assert command == [os.fspath(appimage.resolve()), "--appimage-extract"]
        assert not check
        root = cwd / "squashfs-root"
        icon = root / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps" / "obsidian.png"
        icon.parent.mkdir(parents=True)
        icon.write_text("embedded icon\n", encoding="utf-8")
        (root / "obsidian.desktop").write_text(
            "\n".join(["[Desktop Entry]", "Type=Application", "Name=Obsidian", "Icon=obsidian", ""]),
            encoding="utf-8",
        )

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("core.launcher_builder.subprocess.run", fake_extract)

    result = process_drop(appimage)

    assert result.ok
    launcher = result.target.read_text(encoding="utf-8")
    cached_icons = list(icon_cache.glob("Obsidian-*.png"))
    assert len(cached_icons) == 1
    assert f"Icon={cached_icons[0].resolve()}" in launcher
    assert f"Exec={appimage.resolve()}" in launcher
    assert "--no-sandbox" not in launcher


def test_process_appimage_uses_pending_icon_and_metadata(tmp_path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(desktop))

    icon = tmp_path / "app.png"
    icon.write_text("icon\n", encoding="utf-8")
    appimage = tmp_path / "vendor-tool.appimage"
    appimage.write_text("binary\n", encoding="utf-8")
    metadata = load_desktop_metadata(
        _write_desktop(
            tmp_path / "metadata.desktop",
            [
                "Name=Vendor Tool",
                "Comment=Portable app",
                "Exec=./old.AppImage",
                "Icon=old-icon",
                "Terminal=true",
            ],
        )
    )

    result = process_drop(appimage, icon, metadata)

    assert result.ok
    launcher = result.target.read_text(encoding="utf-8")
    assert "Name=Vendor Tool" in launcher
    assert "Comment=Portable app" in launcher
    assert f"Exec={appimage.resolve()}" in launcher
    assert f"Icon={icon.resolve()}" in launcher
    assert "Terminal=true" in launcher
    assert "old.AppImage" not in launcher


def test_composes_shell_launcher_from_desktop_metadata_and_pending_icon(tmp_path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(desktop))

    pending_icon = tmp_path / "Custom.svg"
    pending_icon.write_text("custom icon\n", encoding="utf-8")
    metadata_launcher = tmp_path / "demo.desktop"
    metadata_launcher.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Metadata Demo",
                "Comment=Metadata comment",
                "Exec=./broken.sh",
                "Path=./broken",
                "Icon=metadata-icon",
                "Terminal=true",
                "Categories=Utility;",
                "StartupNotify=false",
                "",
            ]
        ),
        encoding="utf-8",
    )
    script = tmp_path / "real.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    metadata = load_desktop_metadata(metadata_launcher)

    result = process_drop(script, pending_icon, metadata)

    assert result.ok
    assert result.target == desktop / "Metadata Demo.desktop"
    launcher = result.target.read_text(encoding="utf-8")
    assert "Name=Metadata Demo" in launcher
    assert "Comment=Metadata comment" in launcher
    assert f'Exec="{script.resolve()}"' in launcher
    assert f"Path={tmp_path}" in launcher
    assert "Terminal=true" in launcher
    assert f"Icon={pending_icon.resolve()}" in launcher
    assert "Categories=Utility;" in launcher
    assert "StartupNotify=false" in launcher
    assert "broken" not in launcher


def test_composes_shell_launcher_with_metadata_icon_without_pending_icon(tmp_path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(desktop))

    metadata_launcher = tmp_path / "demo.desktop"
    metadata_launcher.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Demo",
                "Exec=./broken.sh",
                "Path=./broken",
                "Icon=application-default-icon",
                "",
            ]
        ),
        encoding="utf-8",
    )
    script = tmp_path / "real.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    metadata = load_desktop_metadata(metadata_launcher)

    result = process_drop(script, metadata=metadata)

    assert result.ok
    launcher = result.target.read_text(encoding="utf-8")
    assert f'Exec="{script.resolve()}"' in launcher
    assert "Icon=application-default-icon" in launcher
    assert "broken" not in launcher


def test_desktop_drop_is_metadata_only_not_execution(tmp_path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(desktop))

    source = tmp_path / "demo.desktop"
    source.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Demo",
                "Exec=./run.sh",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = process_drop(source)

    assert not result.ok
    assert "metadata" in result.message
    assert not desktop.exists()


def test_rejects_invalid_desktop_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(tmp_path / "Desktop"))
    source = tmp_path / "broken.desktop"
    source.write_text("not a launcher\n", encoding="utf-8")

    try:
        load_desktop_metadata(source)
    except ValueError as exc:
        assert "valid .desktop" in str(exc)
    else:
        raise AssertionError("invalid desktop metadata was accepted")


def _write_desktop(path, lines):
    path.write_text("\n".join(["[Desktop Entry]", "Type=Application", *lines, ""]), encoding="utf-8")
    return path
