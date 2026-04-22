"""Detail panel — dual view (humanized explanation / raw message)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from usdchecker_ui.core.enricher import EnrichedDiagnostic


class DetailPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._toggle = QPushButton("Show raw")
        self._toggle.setCheckable(True)
        self._toggle.toggled.connect(self._on_toggle)

        self._stack = QStackedWidget()
        self._explanation = QTextBrowser()
        self._explanation.setOpenExternalLinks(True)
        self._raw = QTextBrowser()
        self._missing = QLabel("No explanation registered for this rule.")
        self._missing.setStyleSheet("color: #888; padding: 16px;")

        self._stack.addWidget(self._explanation)  # 0
        self._stack.addWidget(self._raw)           # 1
        self._stack.addWidget(self._missing)       # 2

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._toggle)
        layout.addWidget(self._stack, 1)

        self._current: EnrichedDiagnostic | None = None
        self.show_diagnostic(None)

    def show_diagnostic(self, diag: EnrichedDiagnostic | None) -> None:
        self._current = diag
        if diag is None:
            self._explanation.setMarkdown(
                "_Select a diagnostic in the tree._"
            )
            self._raw.setPlainText("")
            self._toggle.setEnabled(False)
            self._toggle.setChecked(False)
            self._stack.setCurrentIndex(0)
            return

        self._raw.setPlainText(diag.diagnostic.message)
        has_explanation = diag.has_pattern
        if has_explanation:
            self._explanation.setMarkdown(self._format_markdown(diag))
        self._toggle.setEnabled(True)
        self._apply_stack(has_explanation)

    def _apply_stack(self, has_explanation: bool) -> None:
        if not has_explanation and not self._toggle.isChecked():
            # Explanation tab requested but none available.
            self._stack.setCurrentIndex(2)
            self._toggle.setEnabled(True)  # user can still jump to raw
            return
        self._stack.setCurrentIndex(1 if self._toggle.isChecked() else 0)

    def _on_toggle(self, checked: bool) -> None:
        self._toggle.setText("Show explanation" if checked else "Show raw")
        if self._current is None:
            return
        self._apply_stack(self._current.has_pattern)

    @staticmethod
    def _format_markdown(diag: EnrichedDiagnostic) -> str:
        parts: list[str] = []
        if diag.title:
            parts.append(f"## {diag.title}")
        if diag.explanation:
            parts.append(diag.explanation)
        if diag.suggestion:
            parts.append("### Suggestion")
            parts.append(diag.suggestion)
        prim = diag.diagnostic.prim_path
        if prim:
            parts.append(f"**Affected prim:** `{prim}`")
        return "\n\n".join(parts)
