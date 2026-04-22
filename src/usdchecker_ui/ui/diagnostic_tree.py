"""Diagnostic tree view + underlying model.

Hierarchy: Severity → Rule → Prim (leaves carry the full EnrichedDiagnostic
via UserRole so the detail panel can read it).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QHeaderView, QTreeView

from usdchecker_ui.core.enricher import EnrichedDiagnostic

DIAG_ROLE = Qt.ItemDataRole.UserRole + 1
SEVERITY_ROLE = Qt.ItemDataRole.UserRole + 2
RULE_ROLE = Qt.ItemDataRole.UserRole + 3

_SEVERITY_LABEL = {"error": "Errors", "warning": "Warnings"}
_SEVERITY_ORDER = ["error", "warning"]


class _RecursiveProxy(QSortFilterProxyModel):
    """Proxy that ANDs severity + rule + free-text filters.

    Uses setRecursiveFilteringEnabled(True) so a matching leaf drags its
    ancestors visible. Qt's default filter hides ancestors whose own row
    text doesn't match — a documented footgun (F16).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRecursiveFilteringEnabled(True)
        self._text = ""
        self._severities: set[str] = set(_SEVERITY_ORDER)
        self._rules: set[str] | None = None  # None = all rules pass

    def set_text(self, text: str) -> None:
        self._text = text.lower().strip()
        self.invalidateFilter()

    def set_severities(self, severities: Iterable[str]) -> None:
        self._severities = set(severities)
        self.invalidateFilter()

    def set_rules(self, rules: set[str] | None) -> None:
        self._rules = rules
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent):  # noqa: N802 — Qt API
        src = self.sourceModel()
        index = src.index(source_row, 0, source_parent)
        if not index.isValid():
            return False

        severity = index.data(SEVERITY_ROLE)
        rule = index.data(RULE_ROLE)

        if severity and severity not in self._severities:
            return False
        if rule is not None and self._rules is not None and rule not in self._rules:
            return False

        if self._text:
            # Search the row label itself AND the diagnostic message if any.
            label = (index.data(Qt.ItemDataRole.DisplayRole) or "").lower()
            diag = index.data(DIAG_ROLE)
            message = (diag.diagnostic.message.lower() if diag else "")
            prim = (diag.diagnostic.prim_path.lower() if diag and diag.diagnostic.prim_path else "")
            hay = label + " " + message + " " + prim
            if self._text not in hay:
                return False

        return True


class DiagnosticTreeView(QTreeView):
    selectionChangedDiag = Signal(object)  # EnrichedDiagnostic | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = QStandardItemModel(self)
        self._model.setHorizontalHeaderLabels(["Diagnostic", "Detail"])
        self._proxy = _RecursiveProxy(self)
        self._proxy.setSourceModel(self._model)
        self.setModel(self._proxy)
        self.setUniformRowHeights(True)
        self.setSortingEnabled(False)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.selectionModel().selectionChanged.connect(self._emit_selection)

    def proxy(self) -> _RecursiveProxy:
        return self._proxy

    def populate(self, diagnostics: Iterable[EnrichedDiagnostic]) -> None:
        # Block selection signals during rebuild to avoid a transient
        # `selectionChangedDiag(None)` leaking to the detail panel (F14).
        sel = self.selectionModel()
        was_blocked = sel.blockSignals(True)
        self._model.removeRows(0, self._model.rowCount())
        grouped: dict[str, dict[str, list[EnrichedDiagnostic]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for d in diagnostics:
            grouped[d.diagnostic.severity][d.diagnostic.rule].append(d)

        for severity in _SEVERITY_ORDER:
            rules_for_sev = grouped.get(severity)
            if not rules_for_sev:
                continue
            sev_label = _SEVERITY_LABEL.get(severity, severity)
            sev_count = sum(len(v) for v in rules_for_sev.values())
            sev_item = QStandardItem(f"{sev_label} ({sev_count})")
            sev_item.setData(severity, SEVERITY_ROLE)
            sev_item.setEditable(False)

            for rule, entries in sorted(rules_for_sev.items()):
                rule_item = QStandardItem(f"{rule} ({len(entries)})")
                rule_item.setEditable(False)
                rule_item.setData(severity, SEVERITY_ROLE)
                rule_item.setData(rule, RULE_ROLE)

                for e in entries:
                    prim = e.diagnostic.prim_path or "(no prim)"
                    leaf = QStandardItem(prim)
                    leaf.setEditable(False)
                    leaf.setData(severity, SEVERITY_ROLE)
                    leaf.setData(rule, RULE_ROLE)
                    leaf.setData(e, DIAG_ROLE)
                    detail = QStandardItem(e.title or "")
                    detail.setEditable(False)
                    rule_item.appendRow([leaf, detail])
                sev_item.appendRow([rule_item, QStandardItem("")])
            self._model.appendRow([sev_item, QStandardItem("")])

        self.expandAll()
        sel.blockSignals(was_blocked)

    def known_rules(self) -> set[str]:
        rules: set[str] = set()
        for row in range(self._model.rowCount()):
            sev = self._model.item(row)
            for r in range(sev.rowCount()):
                rule_item = sev.child(r)
                rule_name = rule_item.data(RULE_ROLE)
                if rule_name:
                    rules.add(rule_name)
        return rules

    def _emit_selection(self, *_args) -> None:
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            self.selectionChangedDiag.emit(None)
            return
        diag = self._proxy.mapToSource(indexes[0]).data(DIAG_ROLE)
        self.selectionChangedDiag.emit(diag)
