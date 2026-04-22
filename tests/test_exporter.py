"""Tests for core.exporter."""

from __future__ import annotations

import json

from usdchecker_ui.core.diagnostic import Diagnostic
from usdchecker_ui.core.enricher import EnrichedDiagnostic
from usdchecker_ui.core.exporter import to_html, to_json, to_markdown


def _sample_diags() -> list[EnrichedDiagnostic]:
    d1 = Diagnostic(
        rule="NormalMapTextureChecker",
        severity="error",
        message="raw 1",
        prim_path="/World/Mat/NormalTex",
        asset_path="red.png",
    )
    d2 = Diagnostic(
        rule="ShaderPropertyTypeConformanceChecker",
        severity="error",
        message="raw 2",
        prim_path="/World/Mat/Shader",
    )
    return [
        EnrichedDiagnostic(
            diagnostic=d1, title="t1", explanation="e1", suggestion="s1",
            has_pattern=True,
        ),
        EnrichedDiagnostic(diagnostic=d2, has_pattern=False),
    ]


def _sample_meta() -> dict:
    return {
        "file_path": "/tmp/foo.usda",
        "date": "2026-04-22T10:00:00",
        "duration_seconds": 1.25,
        "total": 2,
    }


def test_to_json_roundtrips_and_has_expected_schema() -> None:
    payload = to_json(_sample_diags(), _sample_meta())
    parsed = json.loads(payload)
    assert "meta" in parsed and "diagnostics" in parsed
    assert len(parsed["diagnostics"]) == 2
    first = parsed["diagnostics"][0]
    assert first["enrichment"] == {
        "title": "t1",
        "explanation": "e1",
        "suggestion": "s1",
    }
    assert parsed["diagnostics"][1]["enrichment"] is None


def test_to_markdown_has_h1_and_per_rule_sections() -> None:
    md = to_markdown(_sample_diags(), _sample_meta())
    assert md.startswith("# USDChecker UI — report:")
    assert "## NormalMapTextureChecker (1)" in md
    assert "## ShaderPropertyTypeConformanceChecker (1)" in md
    assert "/World/Mat/NormalTex" in md
    assert "| Key | Value |" in md


def test_to_html_is_standalone() -> None:
    doc = to_html(_sample_diags(), _sample_meta())
    assert "<html" in doc
    assert "<style>" in doc
    assert "/World/Mat/NormalTex" in doc
    assert "/World/Mat/Shader" in doc
