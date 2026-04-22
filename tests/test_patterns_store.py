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
    assert "Library/Application Support" in str(p)


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
