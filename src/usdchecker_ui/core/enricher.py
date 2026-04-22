"""Enricher — attach humanized explanations from patterns.yaml to Diagnostics.

A pxr ComplianceChecker rule can emit several distinct raw messages (e.g.
StageMetadataChecker flags "no upAxis", "no metersPerUnit", "no valid
defaultPrim", "upAxis is not 'Y'" — four different problems under the
same rule name). The enricher therefore accepts multiple pattern entries
per rule, each optionally scoped by a `match:` substring that has to
appear in the raw message. The first entry whose substring hits wins,
so a YAML author should list specific entries first and put a generic
catch-all last.

An entry with no `match:` field (or an empty one) matches any message
from that rule — i.e. it is the catch-all.
"""

from __future__ import annotations

from dataclasses import dataclass

from usdchecker_ui.core.diagnostic import Diagnostic

# One humanized entry: either the catch-all for a rule (no `match`) or a
# sub-pattern that only applies when `match` is a substring of the raw
# diagnostic message.
Pattern = dict  # keys: match (optional), title, explanation, suggestion

# Rule name -> ordered list of patterns. Specific-first, catch-all last.
PatternsDict = dict[str, list[Pattern]]


@dataclass(slots=True, frozen=True)
class EnrichedDiagnostic:
    diagnostic: Diagnostic
    title: str | None = None
    explanation: str | None = None
    suggestion: str | None = None
    # True when the rule matched a pattern entry (even if all fields empty).
    # Distinguishes "no pattern registered" from "pattern with empty fields".
    has_pattern: bool = False

    def to_dict(self) -> dict:
        enrichment: dict | None = None
        if self.has_pattern:
            enrichment = {
                "title": self.title,
                "explanation": self.explanation,
                "suggestion": self.suggestion,
            }
        return {
            **self.diagnostic.to_dict(),
            "enrichment": enrichment,
        }


def _match_entry(entries: list[Pattern], message: str) -> Pattern | None:
    """Return the first entry whose `match` substring is in `message`.

    An entry without a `match` field (or with an empty one) is a catch-all
    and matches any message. Order in `entries` is author-controlled, so
    specific entries must come before the catch-all.
    """
    for entry in entries:
        needle = entry.get("match") or ""
        if not needle or needle in message:
            return entry
    return None


def enrich(d: Diagnostic, patterns: PatternsDict) -> EnrichedDiagnostic:
    """Return an EnrichedDiagnostic. Missing pattern -> enrichment=None in dict."""
    entries = patterns.get(d.rule)
    if not entries:
        return EnrichedDiagnostic(diagnostic=d, has_pattern=False)
    entry = _match_entry(entries, d.message)
    if entry is None:
        return EnrichedDiagnostic(diagnostic=d, has_pattern=False)
    return EnrichedDiagnostic(
        diagnostic=d,
        title=entry.get("title"),
        explanation=entry.get("explanation"),
        suggestion=entry.get("suggestion"),
        has_pattern=True,
    )
