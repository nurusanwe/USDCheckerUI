"""Minimal app-wide stylesheet.

Uses `palette(...)` values so colors adapt to macOS light/dark appearance
automatically — important for QCheckBox labels which otherwise render
with the wrong contrast when the app inherits the system dark palette.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

_STYLESHEET = """
QMainWindow { background: palette(window); }
QTreeView { alternate-background-color: palette(alternate-base); }
QTreeView::item:selected { background: palette(highlight); color: palette(highlighted-text); }
QStatusBar { background: palette(window); }
QPushButton { padding: 4px 10px; }

/* Ensure checkbox labels use the theme's window-text color so they
   remain readable on both light and dark backgrounds. Spacing gives
   the label room next to the indicator. */
QCheckBox { color: palette(window-text); spacing: 6px; padding: 2px 4px; }
QCheckBox::indicator { width: 16px; height: 16px; }

QComboBox { color: palette(text); }
QLineEdit { color: palette(text); }
"""


def apply(app: QApplication) -> None:
    app.setStyleSheet(_STYLESHEET)
