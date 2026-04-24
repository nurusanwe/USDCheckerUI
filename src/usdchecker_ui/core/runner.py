"""Runner — runs pxr.UsdUtils.ComplianceChecker and returns Diagnostics.

API contract verified against /Users/rgt/USD/installed/lib/python/pxr/UsdUtils/
complianceChecker.py (constructor at :1008, GetErrors :1034,
GetWarnings :1043, GetFailedChecks :1059, CheckCompliance :1068).

Severity mapping (posed by the accessor, not by parsing text):
    GetErrors()        -> "error"    (internal rule errors)
    GetWarnings()      -> "warning"  (soft findings)
    GetFailedChecks()  -> "error"    (actual rule failures)

Known-shader suppression
------------------------
After the raw diagnostics are parsed, the runner suppresses the
specific `ShaderPropertyTypeConformanceChecker`/"has invalid shader
node" diagnostics whose Shader prim carries an `info:id` listed in
`core.known_shaders.known_shader_ids()`. These identifiers are
declared by `bundled_shaders/shader_definitions.usda` and are
legitimate in the consuming pipeline, but pxr cannot be made aware
of them from Python-only code — see `core/known_shaders.py` for the
full reason. All OTHER diagnostics on those same prims (incorrect
type, invalid implementation source, etc.) pass through untouched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from usdchecker_ui.core.diagnostic import Diagnostic
from usdchecker_ui.core.parser import parse_one

# Exact substring of the pxr ComplianceChecker message emitted at
# complianceChecker.py:
#     self._AddFailedCheck("Shader <%s> has invalid shader node. " %
#                          (prim.GetPath()))
_INVALID_SHADER_NODE_MARKER = "has invalid shader node"
_SHADER_CONFORMANCE_RULE = "ShaderPropertyTypeConformanceChecker"


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a validation run.

    `diagnostics` is the list the UI renders. `suppressed_known_shader_count`
    is how many "has invalid shader node" diagnostics were filtered out
    because the Shader prim carried a `info:id` listed in the bundled
    shader definitions — surfaced in the status bar so a user looking
    for a vanished warning can see something actually happened.
    """
    diagnostics: list[Diagnostic] = field(default_factory=list)
    suppressed_known_shader_count: int = 0


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

    Backward-compatible wrapper around `check_with_result`. Existing
    callers that only care about the diagnostic list keep working;
    the UI uses `check_with_result` to also surface the suppressed
    count.

    Raises RunnerError on load failure. An empty list means the file is
    compliant (possibly after suppressing known-shader warnings).
    """
    return check_with_result(file_path).diagnostics


def check_with_result(file_path: Path) -> CheckResult:
    """Full validation returning both diagnostics and suppression stats."""
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

    raw_diagnostics: list[Diagnostic] = []
    for raw in checker.GetErrors() or []:
        raw_diagnostics.append(parse_one(raw, "error", "errors"))
    for raw in checker.GetWarnings() or []:
        raw_diagnostics.append(parse_one(raw, "warning", "warnings"))
    for raw in checker.GetFailedChecks() or []:
        raw_diagnostics.append(parse_one(raw, "error", "failed_checks"))

    # Suppress "has invalid shader node" diagnostics for prims whose
    # info:id is a bundled known identifier. Re-open the stage once —
    # pxr caches this, so the cost is effectively the cache lookup.
    kept, suppressed = _filter_known_shader_diagnostics(raw_diagnostics, path)
    return CheckResult(diagnostics=kept, suppressed_known_shader_count=suppressed)


def _filter_known_shader_diagnostics(
    diagnostics: list[Diagnostic], usd_path: Path
) -> tuple[list[Diagnostic], int]:
    """Drop the shader-conformance "has invalid shader node" diagnostics
    whose prim carries a bundled-known `info:id`. Returns (kept, count).

    Everything else passes through untouched — crucially, OTHER messages
    from the same rule on the same prim (Incorrect type, invalid
    implementation source, has no sourceType, …) still fire.
    """
    # Fast path: if no diagnostic can possibly match, skip the stage walk.
    candidates = [
        d for d in diagnostics
        if d.rule == _SHADER_CONFORMANCE_RULE
        and _INVALID_SHADER_NODE_MARKER in d.message
        and d.prim_path
    ]
    if not candidates:
        return diagnostics, 0

    from usdchecker_ui.core import known_shaders
    known = known_shaders.known_shader_ids()
    if not known:
        return diagnostics, 0

    # Open the stage once. Failures here shouldn't kill suppression —
    # just fall back to no-op (keep everything), since the user still
    # sees their diagnostics, just with a few extra noise entries.
    try:
        from pxr import Usd, UsdShade
        stage = Usd.Stage.Open(str(usd_path))
    except Exception:  # noqa: BLE001 — any pxr/file error falls back to no-op
        return diagnostics, 0
    if stage is None:
        return diagnostics, 0

    suppressible_paths: set[str] = set()
    for diag in candidates:
        prim = stage.GetPrimAtPath(diag.prim_path)
        if not prim or not prim.IsValid():
            continue
        if not prim.IsA(UsdShade.Shader):
            continue
        shader_id = UsdShade.Shader(prim).GetShaderId()
        if shader_id and shader_id in known:
            suppressible_paths.add(diag.prim_path)

    if not suppressible_paths:
        return diagnostics, 0

    kept: list[Diagnostic] = []
    suppressed = 0
    for diag in diagnostics:
        if (
            diag.rule == _SHADER_CONFORMANCE_RULE
            and _INVALID_SHADER_NODE_MARKER in diag.message
            and diag.prim_path in suppressible_paths
        ):
            suppressed += 1
            continue
        kept.append(diag)
    return kept, suppressed
