from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESKTOP_LAUNCHER = Path.home() / "Desktop" / "linux-dnd-launcher-gate.desktop"
MAIN_PATTERN = os.fspath(PROJECT_ROOT / "main.py")


def matching_pids() -> set[int]:
    result = subprocess.run(
        ["pgrep", "-f", MAIN_PATTERN],
        check=False,
        capture_output=True,
        text=True,
    )
    return {int(pid) for pid in result.stdout.split() if pid.isdigit()}


def terminate_pids(pids: set[int]) -> None:
    for pid in sorted(pids):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def main() -> int:
    if not DESKTOP_LAUNCHER.exists():
        raise FileNotFoundError(f"Desktop launcher neexistuje: {DESKTOP_LAUNCHER}")

    before = matching_pids()
    process = subprocess.Popen(
        ["gio", "launch", os.fspath(DESKTOP_LAUNCHER)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    time.sleep(2)
    new_pids = matching_pids() - before
    print(f"gio running: {process.poll() is None}")
    print(f"new app pids: {' '.join(str(pid) for pid in sorted(new_pids)) or 'none'}")

    terminate_pids(new_pids)
    time.sleep(0.5)

    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()

    remaining = matching_pids() - before
    print(f"remaining new app pids: {' '.join(str(pid) for pid in sorted(remaining)) or 'none'}")

    return 0 if new_pids and not remaining else 1


if __name__ == "__main__":
    raise SystemExit(main())
