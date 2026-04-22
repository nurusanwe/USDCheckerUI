"""Filter bar — severity checkboxes + rule selector + free-text (debounced 200 ms)."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

_ALL_RULES = "— all rules —"


class FilterBar(QWidget):
    textChanged = Signal(str)
    severitiesChanged = Signal(set)
    ruleChanged = Signal(object)  # set[str] | None
    resetRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._err_cb = QCheckBox("Error")
        self._err_cb.setChecked(True)
        self._warn_cb = QCheckBox("Warning")
        self._warn_cb.setChecked(True)
        self._rule_combo = QComboBox()
        self._rule_combo.addItem(_ALL_RULES)
        self._text = QLineEdit()
        self._text.setPlaceholderText("Filter by text / prim…")
        self._reset = QPushButton("Reset")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._err_cb)
        layout.addWidget(self._warn_cb)
        layout.addWidget(self._rule_combo, 1)
        layout.addWidget(self._text, 2)
        layout.addWidget(self._reset)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(
            lambda: self.textChanged.emit(self._text.text())
        )
        self._text.textChanged.connect(lambda _=None: self._debounce.start())

        self._err_cb.toggled.connect(self._emit_severities)
        self._warn_cb.toggled.connect(self._emit_severities)
        self._rule_combo.currentIndexChanged.connect(self._emit_rule)
        self._reset.clicked.connect(self._on_reset)

    def set_available_rules(self, rules: set[str]) -> None:
        current = self._rule_combo.currentText()
        self._rule_combo.blockSignals(True)
        self._rule_combo.clear()
        self._rule_combo.addItem(_ALL_RULES)
        for r in sorted(rules):
            self._rule_combo.addItem(r)
        idx = self._rule_combo.findText(current)
        self._rule_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._rule_combo.blockSignals(False)

    def _emit_severities(self, *_args) -> None:
        sev: set[str] = set()
        if self._err_cb.isChecked():
            sev.add("error")
        if self._warn_cb.isChecked():
            sev.add("warning")
        self.severitiesChanged.emit(sev)

    def _emit_rule(self, idx: int) -> None:
        if idx <= 0:
            self.ruleChanged.emit(None)
        else:
            self.ruleChanged.emit({self._rule_combo.itemText(idx)})

    def _on_reset(self) -> None:
        self._err_cb.setChecked(True)
        self._warn_cb.setChecked(True)
        self._rule_combo.setCurrentIndex(0)
        self._text.clear()
        self.resetRequested.emit()
