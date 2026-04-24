"""Shader plugin paths dialog.

Lists user-configured plugin paths, lets them add / remove, and
re-registers added paths into the live Plug registry so Sdr sees
their shader definitions without an app restart.

pxr.Plug has no un-registration API — removing a path from the
config only takes effect on the next app launch. The dialog
surfaces this with an explicit warning whenever the user removes
a path.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from usdchecker_ui.core import shader_plugins


class ShaderPluginsDialog(QDialog):
    """Modal dialog under Settings → Shader plugin paths…

    Emits `pathsChanged()` whenever the on-disk config has been
    modified AND at least one new path was successfully registered
    with the Plug registry — so the parent window can offer to
    re-validate the current file.
    """

    pathsChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Shader plugin paths")
        self.setMinimumSize(580, 380)

        self._list = QListWidget(self)
        self._list.setAlternatingRowColors(True)

        self._add_dir_btn = QPushButton("Add directory…", self)
        self._add_file_btn = QPushButton("Add plugInfo.json…", self)
        self._remove_btn = QPushButton("Remove", self)
        self._remove_btn.setEnabled(False)

        button_row = QHBoxLayout()
        button_row.addWidget(self._add_dir_btn)
        button_row.addWidget(self._add_file_btn)
        button_row.addStretch(1)
        button_row.addWidget(self._remove_btn)

        self._caveat = QLabel(
            "Adding a path registers its shader definitions immediately "
            "for the next validation. Removing a path only takes effect "
            "on the next app launch (pxr.Plug does not support "
            "un-registration).",
            self,
        )
        self._caveat.setWordWrap(True)
        self._caveat.setStyleSheet("color: palette(mid); font-size: 11pt;")

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_box.rejected.connect(self.accept)
        close_box.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Additional plugInfo.json paths loaded into the Sdr registry "
            "so renderer-specific shader types are recognised during "
            "validation (e.g. renderer-specific or studio-specific shaders).",
            self,
        ))
        layout.itemAt(0).widget().setWordWrap(True)
        layout.addWidget(self._list, 1)
        layout.addLayout(button_row)
        layout.addWidget(self._caveat)
        layout.addWidget(close_box)

        # Wiring
        self._list.itemSelectionChanged.connect(self._update_remove_enabled)
        self._add_dir_btn.clicked.connect(self._on_add_dir)
        self._add_file_btn.clicked.connect(self._on_add_file)
        self._remove_btn.clicked.connect(self._on_remove)

        self._refresh()

    # ---- slots ----------------------------------------------------------

    def _on_add_dir(self) -> None:
        start = str(Path.home())
        picked = QFileDialog.getExistingDirectory(
            self,
            "Pick a directory containing plugInfo.json",
            start,
        )
        if picked:
            self._add_and_register(Path(picked))

    def _on_add_file(self) -> None:
        start = str(Path.home())
        picked_str, _ = QFileDialog.getOpenFileName(
            self,
            "Pick a plugInfo.json file",
            start,
            "plugInfo.json (plugInfo.json)",
        )
        if picked_str:
            self._add_and_register(Path(picked_str))

    def _on_remove(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        path = Path(item.data(0x0100))  # Qt.ItemDataRole.UserRole == 0x0100
        shader_plugins.remove_path(path)
        self._refresh()
        QMessageBox.information(
            self,
            "Path removed",
            f"{path} has been removed from the config.\n\n"
            "Because pxr.Plug does not support un-registration, "
            "the plugin remains live in this process until you "
            "restart USDChecker UI.",
        )

    # ---- helpers --------------------------------------------------------

    def _add_and_register(self, path: Path) -> None:
        """Add `path` to config, then push into the live Plug registry."""
        shader_plugins.add_path(path)
        results = shader_plugins.register_paths([path])
        self._refresh()

        result = results[0]
        if result.ok:
            self.pathsChanged.emit()
            QMessageBox.information(
                self,
                "Plugin registered",
                f"{path}\n\nRegistered with the Sdr registry. "
                "Re-validate the current file to pick up the new "
                "shader definitions.",
            )
        else:
            QMessageBox.warning(
                self,
                "Registration failed",
                f"{path}\n\n{result.error}\n\n"
                "The path is still saved in the config and will be "
                "retried on next app launch.",
            )

    def _refresh(self) -> None:
        self._list.clear()
        for p in shader_plugins.load_configured_paths():
            item = QListWidgetItem(str(p))
            item.setData(0x0100, str(p))  # Qt.ItemDataRole.UserRole
            item.setToolTip(str(p))
            self._list.addItem(item)
        self._update_remove_enabled()

    def _update_remove_enabled(self) -> None:
        self._remove_btn.setEnabled(self._list.currentItem() is not None)
