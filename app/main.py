from __future__ import annotations

import sys


def main() -> int:
    from PyQt6.QtWidgets import QApplication

    from app.ui import ControlMapperApp

    app = QApplication.instance()
    owns_application = app is None
    if app is None:
        app = QApplication(sys.argv)

    window = ControlMapperApp()
    window.show()
    app.setProperty("_citizenbindvkb_window", window)

    if owns_application:
        return app.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())