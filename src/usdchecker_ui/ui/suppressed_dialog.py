"""Audit dialog for known-shader diagnostics that were suppressed.

Answers the user question "what exactly did the tool hide from me?"
without cluttering the main diagnostic tree. Opened from a clickable
indicator on the status bar when the filter fired on a validation pass.
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from usdchecker_ui.core.diagnostic import Diagnostic


class SuppressedDialog(QDialog):
    """Modal listing each diagnostic the known-shader filter removed
    from the current validation pass.

    Read-only. Each row shows the prim path + full raw pxr message.
    """

    def __init__(
        self,
        suppressed: Iterable[Diagnostic],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Suppressed known-shader diagnostics")
        self.setMinimumSize(720, 380)

        intro = QLabel(
            "These diagnostics were produced by pxr.UsdUtils.ComplianceChecker "
            "against shader prims whose <code>info:id</code> matches a shader "
            "definition bundled with USDChecker UI (currently "
            "<code>AdobeStandardMaterial_*</code>). They are almost always "
            "false positives — the prim carries a valid identifier for its "
            "pipeline, and the only reason USD flagged it is that the "
            "validator runs without the Sdr plugin that defines it. The "
            "tool therefore hides them from the main tree to reduce noise, "
            "and lists them here for transparency.",
            self,
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Prim path", "Raw message"])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(False)
        self._tree.setTextElideMode(Qt.TextElideMode.ElideMiddle)

        for diag in suppressed:
            item = QTreeWidgetItem([diag.prim_path or "", diag.message])
            item.setToolTip(1, diag.message)
            self._tree.addTopLevelItem(item)
        self._tree.resizeColumnToContents(0)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.accept)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self._tree, 1)
        layout.addWidget(buttons)
