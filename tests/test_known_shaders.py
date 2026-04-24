"""Tests for core.known_shaders — bundled + user-added shader identifier
suppression sources."""

from __future__ import annotations

from pathlib import Path

import pytest

from usdchecker_ui.core import known_shaders

# -- bundled files --------------------------------------------------------

def test_bundled_dir_contains_at_least_one_usda() -> None:
    """bundled_shaders/ must ship at least one .usda; the PyInstaller
    spec walks this directory and a missing / empty dir would silently
    ship a broken app."""
    files = list(known_shaders.bundled_shader_defs_dir().glob("*.usda"))
    assert files, f"no .usda in {known_shaders.bundled_shader_defs_dir()}"
    # Sanity-check each has non-trivial content.
    for f in files:
        assert f.stat().st_size > 200, f"{f} is suspiciously small"


def test_bundled_covers_adobe_standard_material() -> None:
    _ = pytest.importorskip("pxr.UsdShade")
    ids = known_shaders.known_shader_ids()
    assert "AdobeStandardMaterial_4_0" in ids
    assert "AdobeShadowCatchingMaterial_1_0" in ids


def test_bundled_covers_common_materialx_surfaces() -> None:
    _ = pytest.importorskip("pxr.UsdShade")
    ids = known_shaders.known_shader_ids()
    # Canonical surface-terminal nodes bundled on purpose.
    assert "ND_standard_surface_surfaceshader" in ids
    assert "ND_gltf_pbr_surfaceshader" in ids
    assert "ND_UsdPreviewSurface_surfaceshader" in ids


def test_known_ids_returns_frozenset() -> None:
    _ = pytest.importorskip("pxr.UsdShade")
    assert isinstance(known_shaders.known_shader_ids(), frozenset)


# -- user sources ---------------------------------------------------------

def _redirect_user_config(monkeypatch: pytest.MonkeyPatch, home: Path) -> Path:
    cfg_dir = home / "USDCheckerUI"
    cfg_file = cfg_dir / "known_shader_sources.yaml"
    monkeypatch.setattr(known_shaders, "_USER_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(known_shaders, "_USER_CONFIG_FILE", cfg_file)
    known_shaders.known_shader_ids.cache_clear()
    return cfg_file


def _write_usda_with_shader(path: Path, ident: str) -> Path:
    path.write_text(
        "#usda 1.0\n"
        f"def Shader \"{ident}\" {{\n"
        f"    uniform token info:id = \"{ident}\"\n"
        "    uniform token info:implementationSource = \"id\"\n"
        "}\n",
        encoding="utf-8",
    )
    return path


def test_load_user_sources_empty_when_no_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect_user_config(monkeypatch, tmp_path)
    assert known_shaders.load_user_sources() == []


def test_save_and_load_user_sources_roundtrip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect_user_config(monkeypatch, tmp_path)
    a = tmp_path / "a.usda"
    b = tmp_path / "b.usda"
    known_shaders.save_user_sources([a, b])
    assert known_shaders.load_user_sources() == [a, b]


def test_user_sources_dedupe_on_save(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect_user_config(monkeypatch, tmp_path)
    p = tmp_path / "same.usda"
    known_shaders.save_user_sources([p, p, p])
    assert known_shaders.load_user_sources() == [p]


def test_add_user_source_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect_user_config(monkeypatch, tmp_path)
    p = tmp_path / "plug.usda"
    known_shaders.add_user_source(p)
    known_shaders.add_user_source(p)
    assert known_shaders.load_user_sources() == [p]


def test_remove_user_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect_user_config(monkeypatch, tmp_path)
    a = tmp_path / "a.usda"
    b = tmp_path / "b.usda"
    known_shaders.save_user_sources([a, b])
    known_shaders.remove_user_source(a)
    assert known_shaders.load_user_sources() == [b]


def test_user_added_usda_contributes_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = pytest.importorskip("pxr.UsdShade")
    _redirect_user_config(monkeypatch, tmp_path)
    user_usda = _write_usda_with_shader(
        tmp_path / "karma.usda", "karma_surface_v1"
    )
    known_shaders.add_user_source(user_usda)

    ids = known_shaders.known_shader_ids()
    assert "karma_surface_v1" in ids
    # Bundled IDs are still present.
    assert "AdobeStandardMaterial_4_0" in ids


def test_remove_user_source_drops_its_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = pytest.importorskip("pxr.UsdShade")
    _redirect_user_config(monkeypatch, tmp_path)
    user_usda = _write_usda_with_shader(
        tmp_path / "studio.usda", "StudioXYZ_surface"
    )
    known_shaders.add_user_source(user_usda)
    assert "StudioXYZ_surface" in known_shaders.known_shader_ids()

    known_shaders.remove_user_source(user_usda)
    assert "StudioXYZ_surface" not in known_shaders.known_shader_ids()


def test_malformed_user_yaml_tolerated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_file = _redirect_user_config(monkeypatch, tmp_path)
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(": not yaml", encoding="utf-8")
    with pytest.warns(UserWarning, match="malformed"):
        assert known_shaders.load_user_sources() == []


def test_report_all_sources_lists_bundled_and_user(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = pytest.importorskip("pxr.UsdShade")
    _redirect_user_config(monkeypatch, tmp_path)
    user_usda = _write_usda_with_shader(tmp_path / "u.usda", "custom_X")
    known_shaders.add_user_source(user_usda)

    reports = known_shaders.report_all_sources()
    paths = {str(r.path) for r in reports}
    # Every bundled file is represented.
    for p in known_shaders.bundled_shader_defs_dir().glob("*.usda"):
        assert str(p) in paths
    # User source too.
    assert str(user_usda) in paths
    # Each report carries parsed IDs for ok entries.
    ok_reports = [r for r in reports if r.ok]
    assert any("custom_X" in r.ids for r in ok_reports)


def test_broken_user_source_reports_error_without_killing_others(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = pytest.importorskip("pxr.UsdShade")
    _redirect_user_config(monkeypatch, tmp_path)
    missing = tmp_path / "ghost.usda"  # never created
    good = _write_usda_with_shader(tmp_path / "real.usda", "real_id")
    known_shaders.save_user_sources([missing, good])

    reports = known_shaders.report_all_sources()
    missing_reports = [r for r in reports if r.path == missing]
    assert missing_reports and missing_reports[0].ok is False

    ids = known_shaders.known_shader_ids()
    assert "real_id" in ids
