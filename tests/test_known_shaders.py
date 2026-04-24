"""Tests for core.known_shaders — bundled shader identifiers."""

from __future__ import annotations

import pytest

from usdchecker_ui.core import known_shaders


def test_bundled_file_ships_next_to_module() -> None:
    """The bundled .usda must be present in the source tree — the
    PyInstaller spec references this exact path, so a missing file
    would also break the packaged app silently (empty frozenset at
    runtime → filter becomes a no-op)."""
    path = known_shaders.bundled_shader_defs_path()
    assert path.exists(), f"bundled shader_definitions.usda missing at {path}"
    # Sanity-check size — catches a truncated / corrupt checkout.
    assert path.stat().st_size > 1000, (
        f"bundled file is suspiciously small ({path.stat().st_size} bytes)"
    )


def test_known_ids_includes_adobe_standard_material() -> None:
    _ = pytest.importorskip("pxr.UsdShade")
    ids = known_shaders.known_shader_ids()
    # These two are present in the current snapshot; if the bundled
    # file is refreshed and loses either, the refresh author must
    # update this test knowingly.
    assert "AdobeStandardMaterial_4_0" in ids
    assert "AdobeShadowCatchingMaterial_1_0" in ids


def test_known_ids_returns_frozenset() -> None:
    _ = pytest.importorskip("pxr.UsdShade")
    ids = known_shaders.known_shader_ids()
    assert isinstance(ids, frozenset)


def test_known_ids_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first call parses the .usda; subsequent calls hit the LRU
    cache and do not touch pxr again."""
    _ = pytest.importorskip("pxr.UsdShade")
    # Prime the cache.
    first = known_shaders.known_shader_ids()
    # If it were NOT cached, re-reading after clearing the backing
    # file would return empty. We don't actually delete the file
    # (shared state), but calling twice must yield identical objects
    # since lru_cache returns the same immutable frozenset.
    second = known_shaders.known_shader_ids()
    assert first is second
