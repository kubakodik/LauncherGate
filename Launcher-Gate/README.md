Launcher Gate

Launcher Gate is a small Linux desktop utility for creating ".desktop"
launchers with drag and drop.

It is designed around a simple workflow:

unpack -> run Start Launcher Gate.sh -> drop files -> launcher created

Launcher Gate focuses on fast portable launcher creation without requiring
users to manually edit ".desktop" files, metadata, paths, or permissions.

---

Supported Execution Types

Launcher Gate currently supports:

- ".sh"
- ".py"
- ".AppImage"
- ".appimage"
- ".jar"

Supported icon formats:

- ".png"
- ".svg"
- ".ico"

Supported metadata source:

- ".desktop"

---

Portable Start

Launcher Gate starts through:

./Start\ Launcher\ Gate.sh

The bootstrap script:

- changes into its own folder
- supports portable execution
- works after moving the folder
- prefers local ".venv/bin/python"
- falls back to "python3"

If your file manager opens shell scripts as text, use:

Run as Program

or enable:

Executable Text Files -> Run

in your file manager settings.

---

Create Workflow

Drop a supported execution file:

app.sh
app.py
app.AppImage
app.jar

Launcher Gate immediately creates a desktop launcher.

---

Create Workflow With Custom Icon

Drop:

icon.png + executable

Example:

icon.png + app.py

Launcher Gate creates a launcher using the dropped icon.

---

Metadata / Repair Workflow

Dropped ".desktop" files are treated as:

- metadata sources
- repair/update targets

They are not treated as primary executable sources.

When a ".desktop" file is dropped, Launcher Gate loads metadata such as:

- "Name"
- "Comment"
- "Categories"
- "Terminal"
- "StartupNotify"
- "Icon"

The execution file always controls:

- "Exec="
- "Path="

---


Existing Launcher Repair

Drop:

existing.desktop

Launcher Gate enters repair/update mode.

Example workflows:

desktop only
→ metadata loaded

icon + desktop
→ launcher icon updated

The existing launcher is updated instead of creating a new launcher.

---

Icon Priority

Launcher Gate uses icons in this order:

1. Explicitly dropped icon
2. Extracted AppImage icon
3. Icon from ".desktop" metadata
4. System fallback icon

---

Requirements

- Linux desktop environment
- Python 3
- PyQt6

Recommended environment setup:

python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt

---

Optional Desktop Shortcut

The portable bootstrap uses a shell script instead of a ".desktop" file.

To install a desktop shortcut for Launcher Gate itself:

.venv/bin/python -m tools.install_desktop_launcher

---

Development Checks

Run tests:

.venv/bin/python -m pytest -q

Verify desktop launcher behavior:

.venv/bin/python -m tools.verify_desktop_launch

---

Project Layout

Start Launcher Gate.sh   portable bootstrap launcher
main.py                  application entry point
core/                    launcher generation and detection
ui/                      PyQt6 drag-and-drop interface
icons/                   application icons
tools/                   optional helper utilities
tests/                   regression tests

---

Notes

Launcher Gate marks generated launchers executable and attempts to apply the
GNOME trusted launcher flag when supported.

Desktop environment behavior may still vary depending on:

- desktop environment
- file manager
- security settings
- launcher trust behavior

especially around double-click execution and portable launchers.

---

Feedback

Launcher Gate V1 is an early public release.

Feedback, edge cases, and desktop-environment-specific issues are welcome.
