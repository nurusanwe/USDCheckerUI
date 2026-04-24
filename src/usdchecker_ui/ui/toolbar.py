"""Main toolbar — open / export / VSCode + Settings menu (patterns)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QToolBar, QToolButton


class MainToolbar(QToolBar):
    openRequested = Signal()
    exportRequested = Signal(str)  # "json" | "markdown" | "html"
    editorRequested = Signal()
    editPatternsRequested = Signal()
    reloadPatternsRequested = Signal()
    editKnownShadersRequested = Signal()
    editShaderPluginsRequested = Signal()

    def __init__(self, parent=None):
        super().__init__("Main", parent)
        self.setMovable(False)

        self._open_action = QAction("Open…", self)
        self._open_action.triggered.connect(self.openRequested)
        self.addAction(self._open_action)

        self._export_btn = QToolButton(self)
        self._export_btn.setText("Export")
        self._export_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        export_menu = QMenu(self._export_btn)
        for fmt, label in (("json", "JSON"), ("markdown", "Markdown"), ("html", "HTML")):
            act = QAction(label, export_menu)
            act.triggered.connect(lambda _=False, f=fmt: self.exportRequested.emit(f))
            export_menu.addAction(act)
        self._export_btn.setMenu(export_menu)
        self._export_btn.setEnabled(False)
        self.addWidget(self._export_btn)

        self._editor_action = QAction("Open in VSCode", self)
        self._editor_action.triggered.connect(self.editorRequested)
        self.addAction(self._editor_action)

        self.addSeparator()

        settings_btn = QToolButton(self)
        settings_btn.setText("Settings")
        settings_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        settings_menu = QMenu(settings_btn)
        edit_action = QAction("Edit patterns…", settings_menu)
        edit_action.triggered.connect(self.editPatternsRequested)
        reload_action = QAction("Reload patterns", settings_menu)
        reload_action.triggered.connect(self.reloadPatternsRequested)
        known_shaders_action = QAction(
            "Additional shader definitions…", settings_menu
        )
        known_shaders_action.triggered.connect(self.editKnownShadersRequested)
        shader_plugins_action = QAction(
            "Shader plugin paths… (advanced)", settings_menu
        )
        shader_plugins_action.triggered.connect(self.editShaderPluginsRequested)
        settings_menu.addAction(edit_action)
        settings_menu.addAction(reload_action)
        settings_menu.addSeparator()
        settings_menu.addAction(known_shaders_action)
        settings_menu.addAction(shader_plugins_action)
        settings_btn.setMenu(settings_menu)
        self.addWidget(settings_btn)

    def set_editor_enabled(self, enabled: bool, tooltip: str = "") -> None:
        self._editor_action.setEnabled(enabled)
        self._editor_action.setToolTip(tooltip)

    def set_export_enabled(self, enabled: bool) -> None:
        self._export_btn.setEnabled(enabled)
