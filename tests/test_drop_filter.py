"""Unit tests for the pure drop-filter helper (Qt-free)."""

from __future__ import annotations

from pathlib import Path

from usdchecker_ui.core.drop_filter import ACCEPTED_USD_EXTS, first_accepted_file


def test_first_accepted_returns_first_matching_path() -> None:
    chosen = first_accepted_file(
        ["/tmp/ignored.txt", "/tmp/scene.usda", "/tmp/other.usdc"]
    )
    assert chosen == Path("/tmp/scene.usda")


def test_first_accepted_is_case_insensitive() -> None:
    # Windows Explorer often surfaces uppercase-extension paths.
    chosen = first_accepted_file(["/tmp/SCENE.USDA"])
    assert chosen == Path("/tmp/SCENE.USDA")
    assert chosen.suffix.lower() in ACCEPTED_USD_EXTS


def test_first_accepted_returns_none_when_no_match() -> None:
    assert first_accepted_file(["/tmp/foo.png", "/tmp/bar.exr"]) is None


def test_first_accepted_returns_none_for_empty_list() -> None:
    assert first_accepted_file([]) is None


def test_first_accepted_skips_empty_strings() -> None:
    # QUrl may hand an empty string for a non-local URL; don't crash.
    assert first_accepted_file(["", "/tmp/scene.usdz"]) == Path("/tmp/scene.usdz")


def test_first_accepted_accepts_all_four_usd_extensions() -> None:
    for ext in (".usd", ".usda", ".usdc", ".usdz"):
        assert first_accepted_file([f"/tmp/scene{ext}"]) == Path(f"/tmp/scene{ext}")


def test_accepted_exts_constant_is_immutable() -> None:
    # frozenset contract — prevents a caller from accidentally mutating
    # the shared set at runtime.
    assert isinstance(ACCEPTED_USD_EXTS, frozenset)
    assert {".usd", ".usda", ".usdc", ".usdz"} == ACCEPTED_USD_EXTS


def test_first_accepted_handles_windows_style_paths() -> None:
    # On Windows, QUrl.toLocalFile() returns backslash-separated paths.
    # Path() accepts both on any host; the helper must not add separator
    # assumptions that would break on the opposite platform.
    chosen = first_accepted_file([r"C:\Users\runner\scene.usda"])
    assert chosen is not None
    assert chosen.suffix.lower() == ".usda"
