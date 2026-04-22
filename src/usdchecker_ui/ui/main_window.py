"""Main window — orchestrates drop zone, worker thread, tree, filters, export."""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from usdchecker_ui.core import editor_launcher, exporter, patterns_store
from usdchecker_ui.core.enricher import EnrichedDiagnostic, enrich
from usdchecker_ui.ui.check_worker import CheckWorker
from usdchecker_ui.ui.detail_panel import DetailPanel
from usdchecker_ui.ui.diagnostic_tree import DiagnosticTreeView
from usdchecker_ui.ui.drop_zone import DropZone
from usdchecker_ui.ui.filter_bar import FilterBar
from usdchecker_ui.ui.toolbar import MainToolbar


def _vscode_missing_text(platform: str) -> str:
    """Return the VSCode-missing message appropriate for `platform`.

    Pure function of its argument so tests can exercise every branch on
    any host. Arrows are written as `\\u2192` escapes to prevent a
    copy-paste mishap from silently swapping the glyph for a lookalike.
    """
    arrow = "→"  # RIGHTWARDS ARROW — explicit escape; see F22 in tech spec.
    if platform == "darwin":
        return (
            f"VSCode CLI (`code`) not found. Open VSCode {arrow} Cmd+Shift+P "
            f"{arrow} type 'Shell Command: Install \"code\" command in PATH' "
            f"{arrow} relaunch USDChecker UI."
        )
    if platform.startswith("win"):
        return (
            f"VSCode CLI (`code`) not found. Open VSCode {arrow} Ctrl+Shift+P "
            f"{arrow} type 'Shell: Install \"code\" command in PATH', or "
            f"reinstall VSCode with 'Add to PATH' checked "
            f"{arrow} relaunch USDChecker UI."
        )
    return (
        "VSCode CLI (`code`) not found. Install VSCode and ensure `code` "
        "is on PATH, then relaunch USDChecker UI."
    )


# Exposed for the AC 8 regression test (tests/test_main_window_text.py).
VSCODE_MISSING_TEXT = _vscode_missing_text(sys.platform)

_ERROR_HEADLINE = {
    "FILE_NOT_FOUND": "File not found",
    "USD_LOAD_ERROR": "Could not open USD file",
    "UNKNOWN": "Unexpected error",
    "PATTERNS_ERROR": "Patterns file error",
}


class MainWindow(QMainWindow):
    # Bridge signal to reach the worker thread's run slot. Path is not a
    # registered Qt metatype — pass as str and re-wrap on the worker side.
    runCheck = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("USDChecker UI")
        self.resize(1100, 720)

        self._toolbar = MainToolbar(self)
        self.addToolBar(self._toolbar)

        self._drop_zone = DropZone()
        self._filter_bar = FilterBar()
        self._tree = DiagnosticTreeView()
        self._detail = DetailPanel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._tree)
        splitter.addWidget(self._detail)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._drop_zone)
        layout.addWidget(self._filter_bar)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(container)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready — drop a USD file.")

        # Worker thread.
        self._thread = QThread(self)
        self._worker = CheckWorker()
        self._worker.moveToThread(self._thread)
        self.runCheck.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

        # State.
        self._busy: bool = False
        self._diagnostics: list[EnrichedDiagnostic] = []
        self._current_file: Path | None = None
        self._last_duration: float = 0.0

        # Wiring.
        self._drop_zone.fileDropped.connect(self._on_file_dropped)
        self._toolbar.openRequested.connect(self._on_open_dialog)
        self._toolbar.exportRequested.connect(self._on_export_requested)
        self._toolbar.editorRequested.connect(self._on_editor_requested)
        self._toolbar.editPatternsRequested.connect(self._on_edit_patterns)
        self._toolbar.reloadPatternsRequested.connect(self._on_reload_patterns)
        self._filter_bar.textChanged.connect(self._tree.proxy().set_text)
        self._filter_bar.severitiesChanged.connect(self._tree.proxy().set_severities)
        self._filter_bar.ruleChanged.connect(self._tree.proxy().set_rules)
        self._filter_bar.resetRequested.connect(self._reset_filters)
        self._tree.selectionChangedDiag.connect(self._on_selection_changed)

        self._update_editor_button(None)
        self._toolbar.set_export_enabled(False)

    # ---- slots ------------------------------------------------------------
    def _on_file_dropped(self, path: Path) -> None:
        if self._busy:
            self._toast("Validation in progress — please wait.")
            return
        self._busy = True
        self._current_file = path
        self._drop_zone.set_loaded_file(path)
        self._status.showMessage(f"Validating {path.name}…")
        self.runCheck.emit(str(path))

    def _on_open_dialog(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open a USD file",
            str(Path.home()),
            "USD (*.usd *.usda *.usdc *.usdz)",
        )
        if path_str:
            self._on_file_dropped(Path(path_str))

    def _on_finished(self, diagnostics: list[EnrichedDiagnostic], duration: float) -> None:
        self._busy = False
        self._diagnostics = diagnostics
        self._last_duration = duration
        self._tree.populate(diagnostics)
        self._filter_bar.set_available_rules(self._tree.known_rules())
        self._update_editor_button(self._current_file)
        self._toolbar.set_export_enabled(bool(diagnostics))
        if not diagnostics:
            self._status.showMessage("0 diagnostics — file is clean.")
        else:
            self._status.showMessage(
                f"{len(diagnostics)} diagnostic(s) in {duration:.2f}s."
            )

    def _on_failed(self, code: str, message: str) -> None:
        self._busy = False
        headline = _ERROR_HEADLINE.get(code, _ERROR_HEADLINE["UNKNOWN"])
        QMessageBox.critical(self, headline, f"{headline}\n\n{message}\n\n[code: {code}]")
        self._status.showMessage(f"{headline} — validation aborted.")

    def _on_selection_changed(self, diag) -> None:
        self._detail.show_diagnostic(diag)

    def _on_export_requested(self, fmt: str) -> None:
        if not self._diagnostics:
            self._toast("Nothing to export.")
            return
        default_name = (self._current_file.stem if self._current_file else "report")
        ext = {"json": ".json", "markdown": ".md", "html": ".html"}[fmt]
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export report",
            str(Path.home() / f"{default_name}{ext}"),
            f"{fmt.upper()} (*{ext})",
        )
        if not path_str:
            return
        meta = {
            "file_path": str(self._current_file or ""),
            "date": _dt.datetime.now().isoformat(timespec="seconds"),
            "duration_seconds": round(self._last_duration, 3),
            "total": len(self._diagnostics),
        }
        renderer = {
            "json": exporter.to_json,
            "markdown": exporter.to_markdown,
            "html": exporter.to_html,
        }[fmt]
        Path(path_str).write_text(renderer(self._diagnostics, meta), encoding="utf-8")
        self._toast(f"Exported: {Path(path_str).name}")

    def _on_editor_requested(self) -> None:
        if self._current_file is None or self._current_file.suffix.lower() != ".usda":
            return
        indexes = self._tree.selectionModel().selectedIndexes()
        diag = None
        if indexes:
            from usdchecker_ui.ui.diagnostic_tree import DIAG_ROLE
            diag = self._tree.proxy().mapToSource(indexes[0]).data(DIAG_ROLE)
        prim_path = diag.diagnostic.prim_path if diag else None

        try:
            if prim_path:
                line, unambiguous = editor_launcher.find_prim_line(
                    self._current_file, prim_path
                )
            else:
                line, unambiguous = 1, False
            editor_launcher.open_in_vscode(self._current_file, line)
            if not unambiguous:
                self._toast("Ambiguous prim — opened at root.", duration_ms=5000)
        except editor_launcher.EditorNotAvailableError:
            QMessageBox.warning(self, "VSCode not found", VSCODE_MISSING_TEXT)
        except editor_launcher.EditorLaunchFailedError as exc:
            self._toast(f"VSCode launch failed: {exc}", duration_ms=6000)

    def _on_edit_patterns(self) -> None:
        patterns_store.open_for_edit()
        self._toast("patterns.yaml opened in the system editor.")

    def _on_reload_patterns(self) -> None:
        try:
            fresh = patterns_store.reload()
        except Exception as exc:  # noqa: BLE001 — YAML can raise many types
            QMessageBox.warning(
                self,
                "Invalid patterns.yaml",
                f"Reload failed — malformed file:\n\n{exc}",
            )
            return
        self._diagnostics = [
            enrich(e.diagnostic, fresh) for e in self._diagnostics
        ]
        self._tree.populate(self._diagnostics)
        self._filter_bar.set_available_rules(self._tree.known_rules())
        self._toast("Patterns reloaded.")

    def _reset_filters(self) -> None:
        proxy = self._tree.proxy()
        proxy.set_text("")
        proxy.set_severities({"error", "warning"})
        proxy.set_rules(None)

    def _update_editor_button(self, file: Path | None) -> None:
        if file is None or file.suffix.lower() != ".usda":
            self._toolbar.set_editor_enabled(
                False, "Only available for .usda files"
            )
        else:
            self._toolbar.set_editor_enabled(True, "")

    def _toast(self, message: str, duration_ms: int = 3000) -> None:
        self._status.showMessage(message, duration_ms)

    # ---- shutdown ---------------------------------------------------------
    def shutdown(self) -> None:
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt API
        self.shutdown()
        super().closeEvent(event)
