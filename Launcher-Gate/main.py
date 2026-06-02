from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from ui.drop_window import DropWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Launcher Gate")

    window = DropWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
