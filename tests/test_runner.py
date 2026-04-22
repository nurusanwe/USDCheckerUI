"""Tests for core.runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from usdchecker_ui.core.runner import RunnerError, check


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
