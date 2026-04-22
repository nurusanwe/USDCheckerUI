"""Entry point — warms pxr plugins, then starts the Qt event loop."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from usdchecker_ui.core import plugins_warmup
from usdchecker_ui.ui import theme
from usdchecker_ui.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("Adobe")
    app.setApplicationName("USDCheckerUI")

    # Eager-load pxr plugins BEFORE the event loop to avoid plugin-discovery
    # races on the first drag-drop (see tech-spec F3 / Task 10).
    plugins_warmup.warm()

    theme.apply(app)
    window = MainWindow()
    window.show()
    try:
        return app.exec()
    finally:
        # Guard against MainWindow.closeEvent not firing (e.g. abnormal
        # exit) — otherwise QThread's dtor warns "Destroyed while thread
        # is still running".
        window.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
