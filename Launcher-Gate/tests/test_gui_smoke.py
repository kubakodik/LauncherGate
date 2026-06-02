from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from core.desktop_paths import DESKTOP_DIR_ENV
from ui.drop_window import DropWindow


def test_drop_window_constructs() -> None:
    app = QApplication.instance() or QApplication([])
    window = DropWindow()

    assert window.windowTitle() == "Launcher Gate"
    assert window.drop_zone.acceptDrops()
    assert window.drop_zone.icon_slot.value.text() == ".PNG .SVG .ICO"
    assert window.drop_zone.metadata_slot.value.text() == ".DESKTOP"
    assert window.drop_zone.execution_slot.value.text() == ".SH .PY .APP .JAR"
    assert not window.drop_zone.icon_slot.property("filled")
    assert not window.drop_zone.metadata_slot.property("filled")
    assert not window.drop_zone.execution_slot.property("filled")

    window.close()
    app.processEvents()


def test_drop_zone_icon_then_script_workflow(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(tmp_path / "Desktop"))
    app = QApplication.instance() or QApplication([])
    window = DropWindow()

    icon = tmp_path / "CyberIcon.png"
    icon.write_text("icon\n", encoding="utf-8")
    script = tmp_path / "app.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")

    icon_result = window.drop_zone.handle_local_path(icon)
    assert icon_result.ok
    assert window.drop_zone.pending_icon_path == icon.resolve()

    script_result = window.drop_zone.handle_local_path(script)
    assert script_result.ok
    assert window.drop_zone.pending_icon_path is None
    assert window.drop_zone.icon_slot.value.text() == ".PNG .SVG .ICO"
    assert window.drop_zone.execution_slot.property("filled")
    assert window.drop_zone.execution_slot.value.text() == ".SH .PY .APP .JAR"
    launcher = script_result.target.read_text(encoding="utf-8")
    assert f"Icon={icon.resolve()}" in launcher
    assert "Terminal=false" in launcher

    window.close()
    app.processEvents()


def test_drop_zone_icon_then_desktop_workflow(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(tmp_path / "Desktop"))
    app = QApplication.instance() or QApplication([])
    window = DropWindow()

    icon = tmp_path / "CyberIcon.png"
    icon.write_text("icon\n", encoding="utf-8")
    metadata_launcher = tmp_path / "app.desktop"
    metadata_launcher.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Metadata App",
                "Exec=./broken.sh",
                "Path=./broken",
                "Terminal=true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    script = tmp_path / "app.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")

    icon_result = window.drop_zone.handle_local_path(icon)
    assert icon_result.ok
    assert window.drop_zone.pending_icon_path == icon.resolve()
    assert window.drop_zone.icon_slot.property("filled")
    assert window.drop_zone.icon_slot.value.text() == ".PNG .SVG .ICO"

    metadata_result = window.drop_zone.handle_local_path(metadata_launcher)
    assert metadata_result.ok
    assert window.drop_zone.pending_icon_path == icon.resolve()
    assert window.drop_zone.pending_metadata is not None
    assert window.drop_zone.pending_metadata_path == metadata_launcher.resolve()
    assert window.drop_zone.metadata_slot.property("filled")
    assert window.drop_zone.metadata_slot.value.text() == ".DESKTOP"

    launcher_result = window.drop_zone.handle_local_path(script)
    assert launcher_result.ok
    assert window.drop_zone.pending_icon_path is None
    assert window.drop_zone.pending_metadata is None
    assert window.drop_zone.pending_metadata_path is None
    assert window.drop_zone.icon_slot.value.text() == ".PNG .SVG .ICO"
    assert window.drop_zone.metadata_slot.value.text() == ".DESKTOP"
    assert window.drop_zone.execution_slot.property("filled")
    assert window.drop_zone.execution_slot.value.text() == ".SH .PY .APP .JAR"
    rewritten = launcher_result.target.read_text(encoding="utf-8")
    assert f'Exec="{script.resolve()}"' in rewritten
    assert f"Icon={icon.resolve()}" in rewritten
    assert "Name=Metadata App" in rewritten
    assert "Terminal=true" in rewritten
    assert "broken" not in rewritten
    assert metadata_launcher.exists()

    window.close()
    app.processEvents()


def test_repeated_same_desktop_drop_updates_icon_without_creating_launcher(tmp_path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(desktop))
    app = QApplication.instance() or QApplication([])
    window = DropWindow()

    icon = tmp_path / "Replacement.png"
    icon.write_text("icon\n", encoding="utf-8")
    metadata_launcher = tmp_path / "app.desktop"
    metadata_launcher.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Existing App",
                "Exec=./original.sh",
                "Path=./original",
                "Icon=old-icon",
                "Terminal=false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    metadata_result = window.drop_zone.handle_local_path(metadata_launcher)
    assert metadata_result.ok
    icon_result = window.drop_zone.handle_local_path(icon)
    assert icon_result.ok

    repeat_result = window.drop_zone.handle_local_path(metadata_launcher)

    assert repeat_result.ok
    assert repeat_result.target == metadata_launcher.resolve()
    assert not desktop.exists()
    assert window.drop_zone.pending_icon_path is None
    assert window.drop_zone.pending_metadata is None
    assert window.drop_zone.pending_metadata_path is None
    assert not window.drop_zone.icon_slot.property("filled")
    assert not window.drop_zone.metadata_slot.property("filled")
    assert not window.drop_zone.execution_slot.property("filled")
    rewritten = metadata_launcher.read_text(encoding="utf-8")
    assert f"Icon={icon.resolve()}" in rewritten
    assert "Exec=./original.sh" in rewritten
    assert "Path=./original" in rewritten

    window.close()
    app.processEvents()


def test_repeated_same_jar_desktop_drop_updates_icon_without_creating_launcher(tmp_path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(desktop))
    app = QApplication.instance() or QApplication([])
    window = DropWindow()

    icon = tmp_path / "Replacement.png"
    icon.write_text("icon\n", encoding="utf-8")
    metadata_launcher = tmp_path / "viewer.desktop"
    metadata_launcher.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Existing Viewer",
                "Exec=java -jar ./viewer.jar",
                "Path=./original",
                "Icon=old-icon",
                "Terminal=false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    metadata_result = window.drop_zone.handle_local_path(metadata_launcher)
    assert metadata_result.ok
    icon_result = window.drop_zone.handle_local_path(icon)
    assert icon_result.ok

    repeat_result = window.drop_zone.handle_local_path(metadata_launcher)

    assert repeat_result.ok
    assert repeat_result.target == metadata_launcher.resolve()
    assert not desktop.exists()
    rewritten = metadata_launcher.read_text(encoding="utf-8")
    assert f"Icon={icon.resolve()}" in rewritten
    assert "Exec=java -jar ./viewer.jar" in rewritten
    assert "Path=./original" in rewritten
    assert not window.drop_zone.metadata_slot.property("filled")

    window.close()
    app.processEvents()


def test_drop_zone_python_script_works_without_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(tmp_path / "Desktop"))
    app = QApplication.instance() or QApplication([])
    window = DropWindow()

    script = tmp_path / "app.py"
    script.write_text("print('demo')\n", encoding="utf-8")

    result = window.drop_zone.handle_local_path(script)

    assert result.ok
    assert window.drop_zone.execution_slot.property("filled")
    assert window.drop_zone.execution_slot.value.text() == ".SH .PY .APP .JAR"
    assert "app.py" not in window.drop_zone.execution_slot.value.text()
    launcher = result.target.read_text(encoding="utf-8")
    assert f'"{script.resolve()}"' in launcher
    assert "Terminal=false" in launcher

    window.close()
    app.processEvents()


def test_drop_zone_jar_works_without_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(tmp_path / "Desktop"))
    app = QApplication.instance() or QApplication([])
    window = DropWindow()

    jar = tmp_path / "Viewer.jar"
    jar.write_text("binary\n", encoding="utf-8")

    result = window.drop_zone.handle_local_path(jar)

    assert result.ok
    assert window.drop_zone.execution_slot.property("filled")
    launcher = result.target.read_text(encoding="utf-8")
    assert f'Exec=java -jar "{jar.resolve()}"' in launcher

    window.close()
    app.processEvents()


def test_drop_zone_appimage_script_works_without_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(DESKTOP_DIR_ENV, os.fspath(tmp_path / "Desktop"))
    app = QApplication.instance() or QApplication([])
    window = DropWindow()

    appimage = tmp_path / "Portable.AppImage"
    appimage.write_text("binary\n", encoding="utf-8")

    result = window.drop_zone.handle_local_path(appimage)

    assert result.ok
    assert window.drop_zone.execution_slot.property("filled")
    launcher = result.target.read_text(encoding="utf-8")
    assert f"Exec={appimage.resolve()}" in launcher
    assert "--no-sandbox" not in launcher

    window.close()
    app.processEvents()
