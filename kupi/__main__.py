"""``python3 -m kupi`` entry point.

Also invoked by the top-level ``main.py`` shim (kept for the dev workflow and
``run.sh``) and by the installed ``/usr/bin/kupi`` launcher.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from kupi.app import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("KUPI")
    app.setApplicationDisplayName("KUPI - Kali Universal Package Installer")

    window = MainWindow()

    # Optional file argument (e.g. launched via "Open With" from a file manager).
    for arg in app.arguments()[1:]:
        if os.path.isfile(arg):
            window.load_file(arg)
            break

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
