"""Runner — runs pxr.UsdUtils.ComplianceChecker and returns Diagnostics.

API contract verified against /Users/rgt/USD/installed/lib/python/pxr/UsdUtils/
complianceChecker.py (constructor at :1008, GetErrors :1034,
GetWarnings :1043, GetFailedChecks :1059, CheckCompliance :1068).

Severity mapping (posed by the accessor, not by parsing text):
    GetErrors()        -> "error"    (internal rule errors)
    GetWarnings()      -> "warning"  (soft findings)
    GetFailedChecks()  -> "error"    (actual rule failures)
"""

from __future__ import annotations

from pathlib import Path

from usdchecker_ui.core.diagnostic import Diagnostic
from usdchecker_ui.core.parser import parse_one


class RunnerError(Exception):
    """Raised when the runner cannot produce a diagnostic list at all.

    `code` is one of: "FILE_NOT_FOUND", "USD_LOAD_ERROR", "UNKNOWN".
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def check(file_path: Path) -> list[Diagnostic]:
    """Validate `file_path` and return diagnostics.

    Raises RunnerError on load failure. An empty list means the file is
    compliant.
    """
    path = Path(file_path)
    if not path.exists():
        raise RunnerError("FILE_NOT_FOUND", f"File not found: {path}")

    try:
        from pxr import Tf, UsdUtils
    except ImportError as exc:
        raise RunnerError("UNKNOWN", f"pxr import failed: {exc}") from exc

    try:
        checker = UsdUtils.ComplianceChecker(
            arkit=False,
            skipARKitRootLayerCheck=True,
            rootPackageOnly=False,
            skipVariants=False,
            verbose=False,
            assetLevelChecks=True,
        )
        checker.CheckCompliance(str(path))
    except FileNotFoundError as exc:
        raise RunnerError("FILE_NOT_FOUND", str(exc)) from exc
    except Tf.ErrorException as exc:
        raise RunnerError("USD_LOAD_ERROR", f"USD load failed: {exc}") from exc
    except (RuntimeError, ValueError, OSError) as exc:
        # Corrupted .usdc/.usdz headers + unexpected Tf propagation paths in
        # the wheel surface as RuntimeError/ValueError rather than
        # Tf.ErrorException. Treat them as USD load failures — the caller
        # (UI) uses the code to pick the QMessageBox text per AC 4bis.
        raise RunnerError("USD_LOAD_ERROR", f"USD load failed: {exc}") from exc
    except Exception as exc:
        raise RunnerError("UNKNOWN", f"Unexpected checker error: {exc}") from exc

    diagnostics: list[Diagnostic] = []

    for raw in checker.GetErrors() or []:
        diagnostics.append(parse_one(raw, "error", "errors"))
    for raw in checker.GetWarnings() or []:
        diagnostics.append(parse_one(raw, "warning", "warnings"))
    for raw in checker.GetFailedChecks() or []:
        diagnostics.append(parse_one(raw, "error", "failed_checks"))

    return diagnostics
