"""Drop zone widget — accepts .usd/.usda/.usdc/.usdz files only."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QLabel

from usdchecker_ui.core.drop_filter import first_accepted_file

_PLACEHOLDER = "Drop a .usd / .usda / .usdc / .usdz file here"


class DropZone(QLabel):
    fileDropped = Signal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setText(_PLACEHOLDER)
        self.setMinimumHeight(100)
        self.setStyleSheet(
            'QLabel { border: 2px dashed #888; border-radius: 8px;'
            ' padding: 16px; color: palette(text); }'
            'QLabel[drag="true"] { border-color: #3a7; }'
            'QLabel[loaded="true"] { border-style: solid; border-color: #3a7; }'
        )
        self._loaded: Path | None = None

    def set_loaded_file(self, path: Path | None) -> None:
        """Update the drop-zone label to prominently show the active file.

        Pass None to revert to the placeholder (e.g. after a failed load).
        """
        self._loaded = path
        if path is None:
            self.setProperty("loaded", False)
            self.setText(_PLACEHOLDER)
        else:
            self.setProperty("loaded", True)
            parent_dir = str(path.parent)
            self.setText(
                f'<div style="font-size: 13pt;">'
                f'<b>{path.name}</b>'
                f'</div>'
                f'<div style="font-size: 10pt; color: gray;">{parent_dir}</div>'
                f'<div style="font-size: 9pt; color: gray; margin-top: 6px;">'
                f'Drop another file to replace'
                f'</div>'
            )
        self.style().unpolish(self)
        self.style().polish(self)

    def _first_valid(
        self, event: QDragEnterEvent | QDragMoveEvent | QDropEvent
    ) -> Path | None:
        md = event.mimeData()
        if not md.hasUrls():
            return None
        locals_ = [u.toLocalFile() for u in md.urls() if u.isLocalFile()]
        return first_accepted_file(locals_)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._first_valid(event):
            event.acceptProposedAction()
            self.setProperty("drag", True)
            self.style().unpolish(self)
            self.style().polish(self)
        else:
            event.ignore()
            self.setToolTip("Unsupported format")

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        # Windows Qt requires an explicit accept during move, otherwise
        # the drop phase refuses the payload even if dragEnter accepted.
        # macOS tolerates the default, so this is belt-and-braces there.
        if self._first_valid(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: D401, ANN001
        self.setProperty("drag", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        path = self._first_valid(event)
        self.setProperty("drag", False)
        self.style().unpolish(self)
        self.style().polish(self)
        if path is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self.fileDropped.emit(path)
