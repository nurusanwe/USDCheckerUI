"""Tests for core.patterns_store — layered config + reload."""

from __future__ import annotations

from pathlib import Path

import pytest

from usdchecker_ui.core import patterns_store


def _set_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    """Redirect Path.home() + module constants to an isolated home dir."""
    monkeypatch.setenv("HOME", str(home))
    user_dir = home / "Library" / "Application Support" / "USDCheckerUI"
    user_file = user_dir / "patterns.yaml"
    monkeypatch.setattr(patterns_store, "_USER_DIR", user_dir)
    monkeypatch.setattr(patterns_store, "_USER_FILE", user_file)


def test_user_patterns_path_points_at_app_support(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_home(monkeypatch, tmp_path)
    p = patterns_store.user_patterns_path()
    assert p.parent.name == "USDCheckerUI"
    assert p.name == "patterns.yaml"
    # Path-agnostic: on Windows str(p) uses backslashes, so substring
    # matching on "Library/Application Support" would fail even though
    # the mocked home structure is identical.
    assert "Library" in p.parts
    assert "Application Support" in p.parts


def test_ensure_user_override_creates_then_noop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_home(monkeypatch, tmp_path)
    p = patterns_store.ensure_user_override()
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    # Stub must be empty-by-semantics (so bundled rules still flow through)
    # but syntactically a valid YAML list.
    assert "override the bundled defaults" in content, content
    import yaml
    parsed = yaml.safe_load(content)
    assert parsed == [] or parsed is None, (
        f"fresh user override should parse to empty list, got {parsed!r}"
    )

    p.write_text("- rule: EditedByTest\n  title: Hi\n", encoding="utf-8")
    after = patterns_store.ensure_user_override()
    assert after.read_text(encoding="utf-8") == "- rule: EditedByTest\n  title: Hi\n"


def test_bundled_entries_reach_user_when_override_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fresh-install scenario: user hasn't customized anything yet. All
    bundled entries must still be loaded end-to-end — the empty stub
    must NOT shadow them."""
    _set_home(monkeypatch, tmp_path)
    patterns_store.ensure_user_override()
    merged = patterns_store.load_merged()
    assert "NormalMapTextureChecker" in merged
    assert "ShaderPropertyTypeConformanceChecker" in merged


def test_bundled_covers_every_pxr_rule() -> None:
    """Regression gate: the bundled patterns.yaml must carry an entry
    for every rule currently shipped by pxr.UsdUtils.ComplianceChecker.

    If pxr adds a new rule in a future usd-core release, this test
    fails and signals that the bundled dictionary needs a new entry.
    The alternative — silently shipping an un-enriched rule that shows
    the raw pxr message in the UI — is exactly what patterns.yaml
    exists to prevent.
    """
    pxr_utils = pytest.importorskip("pxr.UsdUtils")
    expected = {r.__name__ for r in pxr_utils.ComplianceChecker().GetRules()}
    bundled = patterns_store._as_index(
        patterns_store._load_yaml_list(patterns_store.bundled_patterns_path()),
        source="bundled",
    )
    missing = expected - set(bundled.keys())
    assert not missing, (
        f"Bundled patterns.yaml missing entries for: {sorted(missing)}. "
        f"Add them to src/usdchecker_ui/core/patterns.yaml with a human "
        f"title / explanation / suggestion."
    )


def test_bundled_entries_have_all_required_fields() -> None:
    """Every bundled entry must carry a non-empty title, explanation,
    and suggestion — otherwise the detail panel renders a blank card."""
    bundled = patterns_store._as_index(
        patterns_store._load_yaml_list(patterns_store.bundled_patterns_path()),
        source="bundled",
    )
    for rule, entry in bundled.items():
        for field in ("title", "explanation", "suggestion"):
            value = entry.get(field)
            assert value and value.strip(), (
                f"Bundled rule {rule!r}: field {field!r} is missing or empty"
            )


def test_load_merged_user_override_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_home(monkeypatch, tmp_path)
    patterns_store.ensure_user_override()
    patterns_store.user_patterns_path().write_text(
        "- rule: NormalMapTextureChecker\n"
        "  title: OVERRIDDEN\n"
        "  explanation: overridden exp\n"
        "  suggestion: overridden sug\n",
        encoding="utf-8",
    )
    merged = patterns_store.load_merged()
    assert merged["NormalMapTextureChecker"]["title"] == "OVERRIDDEN"
    # Bundled-only entry still present.
    assert "ShaderPropertyTypeConformanceChecker" in merged
