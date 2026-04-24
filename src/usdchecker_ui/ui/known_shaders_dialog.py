"""Dialog: manage the list of .usda files that contribute shader IDs
to the known-shader suppression set.

Simpler than the Sdr plugin paths dialog: the user picks a .usda file
(or several), the tool parses each and extracts every `info:id`
declared on Shader prims, and those IDs are unioned into the
suppression set on the next validation pass.

This is the same mechanism the bundled `shader_definitions.usda`
goes through — opening the dialog to user-added files makes the
out-of-the-box "it just works for ASM" experience extensible
without a rebuild.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from usdchecker_ui.core import known_shaders


class KnownShadersDialog(QDialog):
    """Modal under Settings -> Additional shader definitions…

    Emits `sourcesChanged()` after any add/remove so the parent
    window can re-validate the current file automatically.
    """

    sourcesChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Additional shader definitions")
        self.setMinimumSize(720, 440)

        intro = QLabel(
            "Pick <b>.usda files</b> that declare shader identifiers your "
            "pipeline uses. Every <code>def Shader</code> prim inside the "
            "file contributes its <code>info:id</code> value to the set "
            "of shaders USDChecker UI stops flagging as "
            "&ldquo;invalid shader node&rdquo;.<br><br>"
            "This is the same mechanism that already covers Adobe Standard "
            "Material and a small bundled MaterialX set out of the box — "
            "adding a file here extends that set. Examples of files you "
            "might want to add:"
            "<ul>"
            "<li>A <code>shader_definitions.usda</code> shipped with a "
            "renderer install (Houdini Karma, Pixar RenderMan, Arnold, "
            "etc.).</li>"
            "<li>An in-house <code>.usda</code> that declares your studio's "
            "custom shader IDs.</li>"
            "<li>A MaterialX stdlib snapshot converted to USD (ask your "
            "pipeline team if you need a pointer).</li>"
            "</ul>"
            "The existing <i>Shader plugin paths…</i> dialog is a different, "
            "more advanced feature meant for full Sdr plugins that ship a "
            "C++ parser. For the common case of just silencing "
            "renderer-specific identifiers, use THIS dialog.",
            self,
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels([
            "Source", "IDs extracted", "Path / error"
        ])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(False)
        self._tree.setTextElideMode(Qt.TextElideMode.ElideMiddle)

        self._add_btn = QPushButton("Add .usda…", self)
        self._remove_btn = QPushButton("Remove", self)
        self._remove_btn.setEnabled(False)

        button_row = QHBoxLayout()
        button_row.addWidget(self._add_btn)
        button_row.addStretch(1)
        button_row.addWidget(self._remove_btn)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_box.rejected.connect(self.accept)
        close_box.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self._tree, 1)
        layout.addLayout(button_row)
        layout.addWidget(close_box)

        self._tree.itemSelectionChanged.connect(self._update_remove_enabled)
        self._add_btn.clicked.connect(self._on_add)
        self._remove_btn.clicked.connect(self._on_remove)

        self._refresh()

    # ---- slots ----------------------------------------------------------

    def _on_add(self) -> None:
        start = str(Path.home())
        picked, _ = QFileDialog.getOpenFileName(
            self,
            "Pick a .usda file containing shader definitions",
            start,
            "USD files (*.usda *.usd)",
        )
        if not picked:
            return
        path = Path(picked)
        # Sanity-check parse before persisting. If the file has no
        # Shader prims with info:id we warn — the user may have picked
        # the wrong file.
        report = known_shaders._extract_ids_from_usda(path)
        if not report.ok:
            QMessageBox.warning(
                self,
                "Could not parse file",
                f"{path}\n\n{report.error}\n\n"
                "The file was not added.",
            )
            return
        if not report.ids:
            reply = QMessageBox.question(
                self,
                "No shader identifiers found",
                f"{path}\n\nThis file parsed successfully but declares no "
                "<code>def Shader</code> prim with an <code>info:id</code> "
                "value. Adding it will have no effect. Add anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        known_shaders.add_user_source(path)
        self._refresh()
        self.sourcesChanged.emit()

    def _on_remove(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        raw = item.data(0, 0x0100)  # Qt.ItemDataRole.UserRole
        if not raw or not raw.startswith("user:"):
            return  # bundled entries are not removable from the UI
        path = Path(raw[len("user:"):])
        known_shaders.remove_user_source(path)
        self._refresh()
        self.sourcesChanged.emit()

    # ---- helpers --------------------------------------------------------

    def _refresh(self) -> None:
        self._tree.clear()
        bundled_dir = known_shaders.bundled_shader_defs_dir()
        user_paths_set = {str(p) for p in known_shaders.load_user_sources()}

        for report in known_shaders.report_all_sources():
            # Categorise: bundled (read-only) vs user-added (removable).
            is_user = str(report.path) in user_paths_set or not str(
                report.path
            ).startswith(str(bundled_dir))
            origin = "User" if is_user else "Bundled"
            ids_cell = ", ".join(sorted(report.ids)) if report.ids else (
                "(no Shader info:id found)" if report.ok else "— parse error"
            )
            path_or_error = report.error if not report.ok else str(report.path)
            item = QTreeWidgetItem([origin, ids_cell, path_or_error])
            item.setToolTip(2, path_or_error)
            if is_user:
                item.setData(0, 0x0100, f"user:{report.path}")
            self._tree.addTopLevelItem(item)
        self._tree.resizeColumnToContents(0)
        self._tree.resizeColumnToContents(1)
        self._update_remove_enabled()

    def _update_remove_enabled(self) -> None:
        item = self._tree.currentItem()
        removable = bool(item and item.data(0, 0x0100) and
                         item.data(0, 0x0100).startswith("user:"))
        self._remove_btn.setEnabled(removable)
