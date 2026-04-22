"""Parser — turn raw strings from pxr.UsdUtils.ComplianceChecker into Diagnostics.

Three accessors on the checker (GetErrors / GetWarnings / GetFailedChecks) each
produce a distinct message shape. We never parse the severity out of the text —
the caller passes it along with the accessor name (source).

Verified against:
  /Users/rgt/USD/installed/lib/python/pxr/UsdUtils/complianceChecker.py
  (lines 1034 / 1043 / 1059)
"""

from __future__ import annotations

import re

from usdchecker_ui.core.diagnostic import Diagnostic, Severity

# Full-line shapes (one per accessor).
_ERRORS_SHAPE = re.compile(r"^Error checking rule '(?P<rule>[^']+)': (?P<rest>.*)$")
_WARNINGS_SHAPE = re.compile(r"^(?P<msg>.*) \(may violate '(?P<rule>[^']+)'\)$")
_FAILED_CHECKS_SHAPE = re.compile(r"^(?P<msg>.*) \(fails '(?P<rule>[^']+)'\)$")

# Secondary extractors applied to the message body.
_PRIM_ANGLE = re.compile(r"<(?P<prim>/[^>]+)>")
_PRIM_PLAIN = re.compile(r"(?<![<\w])(?P<prim>/[A-Za-z0-9_/.:-]+)")
_ASSET_AT = re.compile(r"@(?P<asset>[^@]+)@")


def _extract_prim(text: str) -> str | None:
    m = _PRIM_ANGLE.search(text)
    if m:
        return m.group("prim")
    m = _PRIM_PLAIN.search(text)
    if m:
        # Strip trailing sentence punctuation that slipped in.
        return m.group("prim").rstrip(".,;:")
    return None


def _extract_asset(text: str) -> str | None:
    m = _ASSET_AT.search(text)
    return m.group("asset") if m else None


def parse_one(raw: str, severity: Severity, source: str) -> Diagnostic:
    """Parse one raw accessor string into a Diagnostic.

    Fallback: if no regex matches the expected source shape, rule="Unknown"
    and raw is preserved verbatim as the message — we never lose the original
    text.
    """
    if source == "errors":
        m = _ERRORS_SHAPE.match(raw)
        if m:
            rest = m.group("rest")
            return Diagnostic(
                rule=m.group("rule"),
                severity=severity,
                message=raw,
                prim_path=_extract_prim(rest),
                asset_path=_extract_asset(rest),
            )
    elif source == "warnings":
        m = _WARNINGS_SHAPE.match(raw)
        if m:
            body = m.group("msg")
            return Diagnostic(
                rule=m.group("rule"),
                severity=severity,
                message=raw,
                prim_path=_extract_prim(body),
                asset_path=_extract_asset(body),
            )
    elif source == "failed_checks":
        m = _FAILED_CHECKS_SHAPE.match(raw)
        if m:
            body = m.group("msg")
            return Diagnostic(
                rule=m.group("rule"),
                severity=severity,
                message=raw,
                prim_path=_extract_prim(body),
                asset_path=_extract_asset(body),
            )

    return Diagnostic(
        rule="Unknown",
        severity=severity,
        message=raw,
        prim_path=None,
        asset_path=None,
    )
