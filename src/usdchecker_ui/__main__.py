"""Entry point — warms pxr plugins, then starts the Qt event loop."""

from __future__ import annotations

import datetime as _dt
import os
import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication

from usdchecker_ui.core import plugins_warmup
from usdchecker_ui.ui import theme
from usdchecker_ui.ui.main_window import MainWindow


def _crash_log_path() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "USDCheckerUI" / "crash.log"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "USDCheckerUI" / "crash.log"
    return Path.home() / ".local" / "state" / "USDCheckerUI" / "crash.log"


def _install_crash_log() -> None:
    # Release Windows builds run with console=False, which swallows stderr.
    # Any exception before Qt comes up would otherwise exit silently; this
    # hook leaves a traceback on disk so a first-run failure is diagnosable.
    previous = sys.excepthook

    def hook(exc_type, exc, tb) -> None:
        try:
            path = _crash_log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            stamp = _dt.datetime.now().isoformat(timespec="seconds")
            body = "".join(traceback.format_exception(exc_type, exc, tb))
            with path.open("a", encoding="utf-8") as f:
                f.write(f"[{stamp}] {exc_type.__name__}: {exc}\n{body}\n")
        except Exception:
            # Never mask the original exception with an I/O failure from
            # the hook itself.
            pass
        previous(exc_type, exc, tb)

    sys.excepthook = hook


def main() -> int:
    _install_crash_log()

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
