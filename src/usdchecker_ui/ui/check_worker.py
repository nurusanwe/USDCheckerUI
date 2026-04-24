"""Check worker — isolates all pxr interaction on a dedicated QThread.

Contract: nothing pxr-typed crosses the thread boundary. The worker emits
`finished(list[EnrichedDiagnostic])` where EnrichedDiagnostic is a frozen
dataclass — safe to pass between threads.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from usdchecker_ui.core.enricher import enrich
from usdchecker_ui.core.patterns_store import load_merged
from usdchecker_ui.core.runner import RunnerError, check_with_result


class CheckWorker(QObject):
    # enriched diagnostics kept for display, duration seconds, list of
    # raw Diagnostic objects suppressed by the known-shader filter.
    # The latter is what the UI shows in the audit dialog — passing the
    # list (not just a count) keeps the filter transparent.
    finished = Signal(list, float, list)
    failed = Signal(str, str)  # code, message

    @Slot(str)
    def run(self, path_str: str) -> None:
        path = Path(path_str)
        started = time.monotonic()
        try:
            result = check_with_result(path)
        except RunnerError as exc:
            self.failed.emit(exc.code, exc.message)
            return
        except Exception as exc:  # noqa: BLE001 — last-resort UI-side guard
            self.failed.emit("UNKNOWN", f"{type(exc).__name__}: {exc}")
            return

        # A broken user-edited patterns.yaml must NOT nuke a successful check.
        # Fall back to no-enrichment if the layered load fails.
        try:
            patterns = load_merged()
        except Exception as exc:  # noqa: BLE001
            patterns = {}
            self.failed.emit(
                "PATTERNS_ERROR",
                f"patterns.yaml invalid, enrichment disabled: {exc}",
            )
            # Do NOT return — the diagnostics themselves are still valid.
        enriched = [enrich(d, patterns) for d in result.diagnostics]
        duration = time.monotonic() - started
        self.finished.emit(enriched, duration, list(result.suppressed_known_shader))
