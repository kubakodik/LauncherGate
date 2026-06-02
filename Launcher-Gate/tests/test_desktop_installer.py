from __future__ import annotations

from pathlib import Path

from tools.install_desktop_launcher import APP_ID, APP_NAME, build_desktop_entry


def test_build_desktop_entry_uses_project_venv_and_gui_mode(tmp_path: Path) -> None:
    content = build_desktop_entry(tmp_path)

    assert "[Desktop Entry]" in content
    assert f"Name={APP_NAME}" in content
    assert f'Exec="{tmp_path / ".venv" / "bin" / "python"}" "{tmp_path / "main.py"}"' in content
    assert f"Icon={tmp_path / 'icons' / 'launcher-gate.svg'}" in content
    assert "Terminal=false" in content
    assert "StartupNotify=true" in content
    assert APP_ID == "linux-dnd-launcher-gate"
