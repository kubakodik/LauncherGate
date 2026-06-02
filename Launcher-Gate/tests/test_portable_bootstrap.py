from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_start_launcher_gate_script_is_portable() -> None:
    start_script = ROOT / "Start Launcher Gate.sh"
    content = start_script.read_text(encoding="utf-8")

    assert content.startswith("#!/bin/bash\n")
    assert 'cd "$(dirname "$0")"' in content
    assert 'if [ -x ".venv/bin/python" ]; then' in content
    assert 'exec ".venv/bin/python" main.py' in content
    assert "exec python3 main.py" in content
    assert os.access(start_script, os.X_OK)


def test_portable_bootstrap_does_not_use_desktop_entry() -> None:
    assert not (ROOT / "Start Launcher Gate.desktop").exists()
