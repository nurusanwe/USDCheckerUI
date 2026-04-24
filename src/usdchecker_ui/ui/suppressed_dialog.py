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

from usdchecker_ui.core import known_shaders
from usdchecker_ui.core.diagnostic import Diagnostic


def _format_known_ids() -> str:
    """Render the list of currently-recognised shader IDs as HTML inline
    code fragments. Updates automatically when the bundled shader
    definitions file is refreshed or if a future release adds a user
    override layer — nothing in this dialog is hardcoded to a specific
    identifier family."""
    ids = sorted(known_shaders.known_shader_ids())
    if not ids:
        return "<i>(none loaded)</i>"
    return ", ".join(f"<code>{i}</code>" for i in ids)


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
            "These diagnostics were produced by "
            "<code>pxr.UsdUtils.ComplianceChecker</code> against shader "
            "prims whose <code>info:id</code> matches one of the shader "
            "definitions currently recognised by USDChecker UI:<br>"
            f"{_format_known_ids()}<br><br>"
            "They are almost always false positives — the prim carries a "
            "valid identifier for its pipeline, and the only reason USD "
            "flagged it is that the validator runs without the Sdr plugin "
            "that defines it. The tool therefore hides them from the main "
            "tree to reduce noise, and lists them here for transparency.",
            self,
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Prim path", "Raw message"])
        self._tree.setRootIsDecorated(False)
        # No alternating row colors: on macOS dark mode Qt picks a harsh
        # black / medium-grey alternation that makes white text unreadable
        # on every other row.
        self._tree.setAlternatingRowColors(False)
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
