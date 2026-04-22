"""Enricher — attach humanized explanations from patterns.yaml to Diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from usdchecker_ui.core.diagnostic import Diagnostic

Pattern = dict  # keys: title, explanation, suggestion
PatternsDict = dict[str, Pattern]


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


def enrich(d: Diagnostic, patterns: PatternsDict) -> EnrichedDiagnostic:
    """Return an EnrichedDiagnostic. Missing pattern -> enrichment=None in dict."""
    pattern = patterns.get(d.rule)
    if pattern is None:
        return EnrichedDiagnostic(diagnostic=d, has_pattern=False)
    return EnrichedDiagnostic(
        diagnostic=d,
        title=pattern.get("title"),
        explanation=pattern.get("explanation"),
        suggestion=pattern.get("suggestion"),
        has_pattern=True,
    )
