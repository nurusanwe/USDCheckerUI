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
    # "raw" doesn't hit any specific match, so the rule's catch-all
    # entry must fire and still provide a title.
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


# --- sub-pattern matching --------------------------------------------------

def _patterns_from(entries: list) -> dict:
    """Build a PatternsDict from a list of bare entry dicts (test helper)."""
    out: dict = {}
    for e in entries:
        out.setdefault(e["rule"], []).append(e)
    return out


def test_subpattern_specific_match_wins_over_catchall() -> None:
    patterns = _patterns_from([
        {"rule": "Foo", "match": "alpha", "title": "SPECIFIC_A"},
        {"rule": "Foo", "match": "beta", "title": "SPECIFIC_B"},
        {"rule": "Foo", "title": "CATCH_ALL"},
    ])
    d = Diagnostic(rule="Foo", severity="error", message="... alpha ...")
    assert enrich(d, patterns).title == "SPECIFIC_A"
    d = Diagnostic(rule="Foo", severity="error", message="... beta ...")
    assert enrich(d, patterns).title == "SPECIFIC_B"
    d = Diagnostic(rule="Foo", severity="error", message="... unknown ...")
    assert enrich(d, patterns).title == "CATCH_ALL"


def test_subpattern_first_match_wins_even_if_several_could_match() -> None:
    # Order matters. The first entry whose `match` is in the message wins.
    patterns = _patterns_from([
        {"rule": "Foo", "match": "apple", "title": "FIRST"},
        {"rule": "Foo", "match": "pie", "title": "SECOND"},
    ])
    d = Diagnostic(rule="Foo", severity="error", message="apple pie is good")
    assert enrich(d, patterns).title == "FIRST"


def test_subpattern_no_catchall_and_no_match_yields_no_enrichment() -> None:
    patterns = _patterns_from([
        {"rule": "Foo", "match": "banana", "title": "B"},
    ])
    d = Diagnostic(rule="Foo", severity="error", message="apple pie")
    enriched = enrich(d, patterns)
    assert enriched.has_pattern is False
    assert enriched.title is None


def test_subpattern_empty_match_treated_as_catchall() -> None:
    # `match: ""` should behave exactly like a missing `match:` key.
    patterns = _patterns_from([
        {"rule": "Foo", "match": "", "title": "OK"},
    ])
    d = Diagnostic(rule="Foo", severity="error", message="anything")
    assert enrich(d, patterns).title == "OK"


# --- real-world: StageMetadataChecker four sub-cases -----------------------
# These exercise the exact substrings bundled patterns.yaml is authored
# against. If someone reorders the file or tweaks a `match:` string and
# breaks the mapping, these fail.

def test_stage_metadata_upaxis_missing_hits_upaxis_card() -> None:
    patterns = load_merged()
    d = Diagnostic(
        rule="StageMetadataChecker",
        severity="error",
        message="Stage does not specify an upAxis.",
    )
    enriched = enrich(d, patterns)
    assert enriched.title is not None
    assert "upAxis" in enriched.title
    # The defaultPrim / metersPerUnit cards MUST NOT fire for this message.
    assert "defaultPrim" not in enriched.title
    assert "metersPerUnit" not in enriched.title


def test_stage_metadata_defaultprim_hits_defaultprim_card() -> None:
    patterns = load_merged()
    d = Diagnostic(
        rule="StageMetadataChecker",
        severity="error",
        message="Stage has missing or invalid defaultPrim.",
    )
    enriched = enrich(d, patterns)
    # This is the bug the user reported — the defaultPrim message must
    # NOT land on the "upAxis or metersPerUnit" card.
    assert enriched.title is not None
    assert "defaultPrim" in enriched.title
    assert "upAxis" not in enriched.title


def test_stage_metadata_meters_per_unit_hits_its_own_card() -> None:
    patterns = load_merged()
    d = Diagnostic(
        rule="StageMetadataChecker",
        severity="error",
        message="Stage does not specify its linear scale in metersPerUnit.",
    )
    enriched = enrich(d, patterns)
    assert enriched.title is not None
    assert "metersPerUnit" in enriched.title
    assert "defaultPrim" not in enriched.title


def test_stage_metadata_non_y_upaxis_hits_consumer_card() -> None:
    patterns = load_merged()
    d = Diagnostic(
        rule="StageMetadataChecker",
        severity="error",
        message="Stage specifies upAxis 'Z'. upAxis should be 'Y'.",
    )
    enriched = enrich(d, patterns)
    assert enriched.title is not None
    # "Stage `upAxis` is not `Y`" expected — must NOT be the "does not
    # declare upAxis" card.
    assert "not" in enriched.title.lower() and "Y" in enriched.title
    assert "does not declare" not in enriched.title


# --- real-world: NormalMapTextureChecker sub-cases -------------------------

def test_normal_map_sourcecolorspace_hits_raw_card() -> None:
    patterns = load_merged()
    d = Diagnostic(
        rule="NormalMapTextureChecker",
        severity="error",
        message=(
            "UsdUVTexture prim </M/Tex> that reads Normal Map @n.png@ "
            "should set inputs:sourceColorSpace to 'raw'."
        ),
    )
    enriched = enrich(d, patterns)
    assert enriched.title is not None
    assert "sourceColorSpace" in enriched.title or "raw" in enriched.title


def test_normal_map_missing_scale_bias_hits_scale_card() -> None:
    patterns = load_merged()
    d = Diagnostic(
        rule="NormalMapTextureChecker",
        severity="error",
        message=(
            "UsdUVTexture prim </M/Tex> reads 8 bit Normal Map @n.png@, "
            "which requires that inputs:scale be set to (2, 2, 2, 1) "
            "and inputs:bias be set to (-1, -1, -1, 0)."
        ),
    )
    enriched = enrich(d, patterns)
    assert enriched.title is not None
    assert "scale" in enriched.title.lower()


# --- to_dict schema (unchanged) --------------------------------------------

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
