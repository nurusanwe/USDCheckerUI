"""Tests for core.runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from usdchecker_ui.core.diagnostic import Diagnostic
from usdchecker_ui.core.runner import (
    RunnerError,
    _filter_known_shader_diagnostics,
    check,
    check_with_result,
)


def test_valid_usda_returns_empty(valid_usda_path: Path) -> None:
    result = check(valid_usda_path)
    # Don't pin on `result == []` — the USD rule set evolves across patch
    # releases within our `>=25.11,<27` range. Assert instead that none of
    # the rules our fixtures are designed to trigger are present, and that
    # whatever slipped in is not an `error`.
    rules = {d.rule for d in result}
    assert "ShaderPropertyTypeConformanceChecker" not in rules, result
    assert "NormalMapTextureChecker" not in rules, result
    assert not any(d.severity == "error" for d in result), (
        f"unexpected errors on the clean fixture: {result!r}"
    )


def test_invalid_usda_flags_shader_property(invalid_usda_path: Path) -> None:
    result = check(invalid_usda_path)
    rules = {d.rule for d in result}
    assert "ShaderPropertyTypeConformanceChecker" in rules, rules
    offending = [
        d for d in result if d.rule == "ShaderPropertyTypeConformanceChecker"
    ]
    assert any(d.severity == "error" for d in offending)


def test_normalmap_invalid_flags_normalmap_checker(
    normalmap_invalid_usda_path: Path,
) -> None:
    result = check(normalmap_invalid_usda_path)
    rules = {d.rule for d in result}
    assert "NormalMapTextureChecker" in rules, rules


def test_usdz_valid_is_clean(usdz_path: Path) -> None:
    result = check(usdz_path)
    rules = {d.rule for d in result}
    assert "ShaderPropertyTypeConformanceChecker" not in rules, result
    assert "NormalMapTextureChecker" not in rules, result


def test_large_corpus_smoke(large_corpus_path: Path, caplog) -> None:
    result = check(large_corpus_path)
    assert isinstance(result, list)
    caplog.set_level("INFO")
    # Informational dump so the dev can eyeball order-of-magnitude manually.
    print(f"[large corpus] {large_corpus_path.name}: {len(result)} diagnostics")


def test_nonexistent_file_raises_file_not_found() -> None:
    with pytest.raises(RunnerError) as exc_info:
        check(Path("/nonexistent/does-not-exist.usd"))
    assert exc_info.value.code == "FILE_NOT_FOUND"


# --- known-shader suppression filter -------------------------------------

def _write_usda(path: Path, shader_id: str) -> Path:
    """Write a minimal .usda declaring a single Shader prim with `info:id`."""
    path.write_text(
        "#usda 1.0\n"
        "def Xform \"World\" {\n"
        "    def Material \"Mat\" {\n"
        f"        def Shader \"Look\" {{\n"
        f"            uniform token info:id = \"{shader_id}\"\n"
        "            uniform token info:implementationSource = \"id\"\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    return path


def test_filter_suppresses_known_shader_invalid_node(tmp_path: Path) -> None:
    _ = pytest.importorskip("pxr.UsdShade")
    usd = _write_usda(tmp_path / "known.usda", "AdobeStandardMaterial_4_0")
    diag = Diagnostic(
        rule="ShaderPropertyTypeConformanceChecker",
        severity="error",
        message="Shader </World/Mat/Look> has invalid shader node.",
        prim_path="/World/Mat/Look",
    )
    kept, count = _filter_known_shader_diagnostics([diag], usd)
    assert kept == []
    assert count == 1


def test_filter_keeps_unknown_shader_id(tmp_path: Path) -> None:
    _ = pytest.importorskip("pxr.UsdShade")
    usd = _write_usda(tmp_path / "unknown.usda", "SomeRandomShader")
    diag = Diagnostic(
        rule="ShaderPropertyTypeConformanceChecker",
        severity="error",
        message="Shader </World/Mat/Look> has invalid shader node.",
        prim_path="/World/Mat/Look",
    )
    kept, count = _filter_known_shader_diagnostics([diag], usd)
    assert kept == [diag]
    assert count == 0


def test_filter_keeps_other_messages_on_known_shader_prim(tmp_path: Path) -> None:
    """Only 'has invalid shader node' is suppressed — other
    ShaderPropertyTypeConformance diagnostics on the SAME prim must
    still fire (e.g. "Incorrect type for ..." from a genuine type
    mismatch on an input)."""
    _ = pytest.importorskip("pxr.UsdShade")
    usd = _write_usda(tmp_path / "known.usda", "AdobeStandardMaterial_4_0")
    incorrect_type = Diagnostic(
        rule="ShaderPropertyTypeConformanceChecker",
        severity="error",
        message="Incorrect type for </World/Mat/Look.inputs:foo>. "
                "Expected 'color3f'; got 'float3'.",
        prim_path="/World/Mat/Look",
    )
    no_sourcetype = Diagnostic(
        rule="ShaderPropertyTypeConformanceChecker",
        severity="error",
        message="Shader </World/Mat/Look> has no sourceType.",
        prim_path="/World/Mat/Look",
    )
    kept, count = _filter_known_shader_diagnostics(
        [incorrect_type, no_sourcetype], usd
    )
    assert kept == [incorrect_type, no_sourcetype]
    assert count == 0


def test_filter_keeps_other_rules(tmp_path: Path) -> None:
    _ = pytest.importorskip("pxr.UsdShade")
    usd = _write_usda(tmp_path / "known.usda", "AdobeStandardMaterial_4_0")
    normal_map = Diagnostic(
        rule="NormalMapTextureChecker",
        severity="error",
        # Intentionally contains "has invalid shader node" as a red herring
        # — a different rule MUST NOT be suppressed even if its message
        # happens to contain the marker substring.
        message="something has invalid shader node wording",
        prim_path="/World/Mat/Look",
    )
    kept, count = _filter_known_shader_diagnostics([normal_map], usd)
    assert kept == [normal_map]
    assert count == 0


def test_filter_no_op_on_empty_input(tmp_path: Path) -> None:
    usd = _write_usda(tmp_path / "known.usda", "AdobeStandardMaterial_4_0")
    kept, count = _filter_known_shader_diagnostics([], usd)
    assert kept == []
    assert count == 0


def test_filter_mix_of_suppressed_and_kept(tmp_path: Path) -> None:
    """A .usda with BOTH a known-shader prim and an unrelated prim:
    the filter suppresses only the known-shader 'invalid node' hit."""
    _ = pytest.importorskip("pxr.UsdShade")
    usd = tmp_path / "mixed.usda"
    usd.write_text(
        "#usda 1.0\n"
        "def Xform \"World\" {\n"
        "    def Material \"MatKnown\" {\n"
        "        def Shader \"Look\" {\n"
        "            uniform token info:id = \"AdobeStandardMaterial_4_0\"\n"
        "            uniform token info:implementationSource = \"id\"\n"
        "        }\n"
        "    }\n"
        "    def Material \"MatUnknown\" {\n"
        "        def Shader \"Look\" {\n"
        "            uniform token info:id = \"MysteryShader\"\n"
        "            uniform token info:implementationSource = \"id\"\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    diags = [
        Diagnostic(
            rule="ShaderPropertyTypeConformanceChecker",
            severity="error",
            message="Shader </World/MatKnown/Look> has invalid shader node.",
            prim_path="/World/MatKnown/Look",
        ),
        Diagnostic(
            rule="ShaderPropertyTypeConformanceChecker",
            severity="error",
            message="Shader </World/MatUnknown/Look> has invalid shader node.",
            prim_path="/World/MatUnknown/Look",
        ),
    ]
    kept, count = _filter_known_shader_diagnostics(diags, usd)
    assert count == 1
    assert len(kept) == 1
    assert kept[0].prim_path == "/World/MatUnknown/Look"


def test_check_with_result_reports_suppressed_count(tmp_path: Path) -> None:
    """End-to-end: feed ComplianceChecker a known-ID Shader prim and
    verify check_with_result returns a non-zero suppressed count while
    the resulting diagnostics list is clean."""
    _ = pytest.importorskip("pxr.UsdShade")
    usd = _write_usda(tmp_path / "e2e.usda", "AdobeStandardMaterial_4_0")
    result = check_with_result(usd)
    # The raw ComplianceChecker would emit at least one
    # ShaderPropertyTypeConformanceChecker / "has invalid shader node"
    # diagnostic for this prim; after suppression it should be gone.
    offending = [
        d for d in result.diagnostics
        if d.rule == "ShaderPropertyTypeConformanceChecker"
        and "has invalid shader node" in d.message
    ]
    assert offending == [], (
        f"known-shader 'invalid shader node' leaked through: {offending}"
    )
    assert result.suppressed_known_shader_count >= 1, result
