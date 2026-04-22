"""Tests for core.enricher + default patterns."""

from __future__ import annotations

from usdchecker_ui.core.diagnostic import Diagnostic
from usdchecker_ui.core.enricher import EnrichedDiagnostic, enrich
from usdchecker_ui.core.patterns_store import load_merged


def test_default_patterns_has_at_least_two_entries() -> None:
    patterns = load_merged()
    assert len(patterns) >= 2
    assert "NormalMapTextureChecker" in patterns
    assert "ShaderPropertyTypeConformanceChecker" in patterns


def test_enrich_with_known_rule_returns_title() -> None:
    patterns = load_merged()
    d = Diagnostic(rule="NormalMapTextureChecker", severity="error", message="raw")
    enriched = enrich(d, patterns)
    assert enriched.title is not None
    assert enriched.explanation is not None


def test_enrich_with_unknown_rule_returns_none() -> None:
    d = Diagnostic(rule="NotARealRule", severity="error", message="raw")
    enriched = enrich(d, {})
    assert enriched.title is None
    assert enriched.explanation is None
    assert enriched.suggestion is None


def test_to_dict_schema_matches_ac12() -> None:
    d = Diagnostic(
        rule="Foo",
        severity="warning",
        message="raw",
        prim_path="/A/B",
        asset_path="tex.png",
        layer=None,
    )
    enriched = EnrichedDiagnostic(
        diagnostic=d,
        title="t",
        explanation="e",
        suggestion="s",
        has_pattern=True,
    )
    payload = enriched.to_dict()
    # AC 12 schema: {rule, severity, message, prim_path, asset_path, layer,
    # enrichment: {title, explanation, suggestion} | null}
    for key in ("rule", "severity", "message", "prim_path", "asset_path", "layer", "enrichment"):
        assert key in payload
    assert payload["enrichment"] == {
        "title": "t",
        "explanation": "e",
        "suggestion": "s",
    }


def test_to_dict_enrichment_null_when_missing() -> None:
    d = Diagnostic(rule="Unknown", severity="error", message="raw")
    enriched = EnrichedDiagnostic(diagnostic=d, has_pattern=False)
    assert enriched.to_dict()["enrichment"] is None


def test_to_dict_enrichment_present_even_with_empty_fields() -> None:
    # has_pattern=True means a pattern entry exists — even if all strings
    # are empty, enrichment must be an object so downstream can tell
    # "pattern with empty fields" from "no pattern registered".
    d = Diagnostic(rule="FooRule", severity="error", message="raw")
    enriched = EnrichedDiagnostic(
        diagnostic=d, title="", explanation="", suggestion="", has_pattern=True
    )
    assert enriched.to_dict()["enrichment"] == {
        "title": "",
        "explanation": "",
        "suggestion": "",
    }
