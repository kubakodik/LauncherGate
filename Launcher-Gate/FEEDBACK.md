# Feedback

Launcher Gate V1 is focused on the core launcher workflow:

- `.sh`
- `.py`
- `.AppImage`
- `.jar`
- optional icon metadata
- optional `.desktop` metadata

When reporting an issue, include:

- Linux distribution and desktop environment
- File type you dropped
- Whether the generated launcher appeared on the desktop
- Whether double-click execution worked
- Any terminal output if you started Launcher Gate from a terminal

Known platform-sensitive areas:

- file manager handling of executable shell scripts
- `.desktop` trust mode
- AppImage icon extraction
- Java runtime availability for `.jar` launchers
