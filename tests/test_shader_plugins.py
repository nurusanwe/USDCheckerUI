"""Tests for core.shader_plugins — user-configured shader plugin paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from usdchecker_ui.core import shader_plugins


def _redirect_config(monkeypatch: pytest.MonkeyPatch, home: Path) -> Path:
    """Isolate the YAML config in a tmp dir so tests don't touch the
    real user profile."""
    cfg_dir = home / "USDCheckerUI"
    cfg_file = cfg_dir / "shader_plugins.yaml"
    monkeypatch.setattr(shader_plugins, "_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(shader_plugins, "_CONFIG_FILE", cfg_file)
    return cfg_file


def _write_valid_plugin(dir_: Path, name: str) -> Path:
    """Write a minimal valid plugInfo.json in `dir_`. Returns `dir_`."""
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / "plugInfo.json").write_text(
        json.dumps({
            "Plugins": [{
                "Name": name,
                "Type": "resource",
                "Info": {"ShaderResources": {}},
                "LibraryPath": "",
                "Root": ".",
            }]
        }),
        encoding="utf-8",
    )
    return dir_


# -- config read / write ---------------------------------------------------

def test_load_returns_empty_when_no_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect_config(monkeypatch, tmp_path)
    assert shader_plugins.load_configured_paths() == []


def test_save_then_load_roundtrips(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect_config(monkeypatch, tmp_path)
    paths = [tmp_path / "plugA", tmp_path / "plugB"]
    shader_plugins.save_configured_paths(paths)
    assert shader_plugins.load_configured_paths() == paths


def test_save_dedupes_by_string(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect_config(monkeypatch, tmp_path)
    p = tmp_path / "plugA"
    shader_plugins.save_configured_paths([p, p, p])
    assert shader_plugins.load_configured_paths() == [p]


def test_load_tolerates_malformed_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_file = _redirect_config(monkeypatch, tmp_path)
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(": : :  totally not yaml", encoding="utf-8")
    with pytest.warns(UserWarning, match="malformed"):
        assert shader_plugins.load_configured_paths() == []


def test_load_tolerates_non_list_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_file = _redirect_config(monkeypatch, tmp_path)
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text("a_string_not_a_list\n", encoding="utf-8")
    assert shader_plugins.load_configured_paths() == []


def test_load_skips_empty_and_non_string_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_file = _redirect_config(monkeypatch, tmp_path)
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(
        "- /valid/path\n"
        "- ''\n"
        "- 42\n"
        "- '   '\n"
        "- /another/valid\n",
        encoding="utf-8",
    )
    loaded = shader_plugins.load_configured_paths()
    assert loaded == [Path("/valid/path"), Path("/another/valid")]


# -- add / remove ----------------------------------------------------------

def test_add_path_appends_new_absolute_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect_config(monkeypatch, tmp_path)
    p = tmp_path / "plugA"
    p.mkdir()
    result = shader_plugins.add_path(p)
    assert p.resolve() in [Path(str(x)) for x in result]
    assert shader_plugins.load_configured_paths()[0] == p.resolve()


def test_add_path_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect_config(monkeypatch, tmp_path)
    p = tmp_path / "plugA"
    p.mkdir()
    shader_plugins.add_path(p)
    shader_plugins.add_path(p)
    shader_plugins.add_path(p)
    assert len(shader_plugins.load_configured_paths()) == 1


def test_remove_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect_config(monkeypatch, tmp_path)
    a = tmp_path / "plugA"
    b = tmp_path / "plugB"
    a.mkdir()
    b.mkdir()
    shader_plugins.save_configured_paths([a, b])
    remaining = shader_plugins.remove_path(a)
    assert remaining == [b]
    assert shader_plugins.load_configured_paths() == [b]


def test_remove_path_noop_when_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect_config(monkeypatch, tmp_path)
    a = tmp_path / "plugA"
    a.mkdir()
    shader_plugins.save_configured_paths([a])
    # Remove a path that was never configured — should leave state alone.
    shader_plugins.remove_path(tmp_path / "ghost")
    assert shader_plugins.load_configured_paths() == [a]


# -- pxr registration ------------------------------------------------------

def test_register_paths_reports_missing_path() -> None:
    ghost = Path("/definitely/not/a/real/path/XYZ")
    results = shader_plugins.register_paths([ghost])
    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].path == ghost
    assert "does not exist" in (results[0].error or "")


def test_register_paths_succeeds_on_valid_dir(tmp_path: Path) -> None:
    _ = pytest.importorskip("pxr.Plug")
    plug_dir = _write_valid_plugin(tmp_path / "myShaderPlug", "myShaderPlug_test")
    results = shader_plugins.register_paths([plug_dir])
    assert len(results) == 1
    assert results[0].ok is True, results[0].error
    # And the plugin is now visible in the live registry.
    from pxr import Plug
    names = {p.name for p in Plug.Registry().GetAllPlugins()}
    assert "myShaderPlug_test" in names


def test_register_paths_succeeds_on_direct_plugInfo_file(tmp_path: Path) -> None:
    _ = pytest.importorskip("pxr.Plug")
    plug_dir = _write_valid_plugin(tmp_path / "directFilePlug", "directFilePlug_test")
    results = shader_plugins.register_paths([plug_dir / "plugInfo.json"])
    assert results[0].ok is True, results[0].error


def test_register_paths_independent_per_path(tmp_path: Path) -> None:
    """One broken path must not stop the others from registering."""
    _ = pytest.importorskip("pxr.Plug")
    good = _write_valid_plugin(tmp_path / "goodPlug", "goodPlug_test")
    bad = Path("/no/such/dir/here")
    results = shader_plugins.register_paths([bad, good])
    assert results[0].ok is False
    assert results[1].ok is True
    from pxr import Plug
    names = {p.name for p in Plug.Registry().GetAllPlugins()}
    assert "goodPlug_test" in names


def test_register_configured_registers_from_disk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = pytest.importorskip("pxr.Plug")
    _redirect_config(monkeypatch, tmp_path)
    plug_dir = _write_valid_plugin(tmp_path / "fromDiskPlug", "fromDiskPlug_test")
    shader_plugins.save_configured_paths([plug_dir])
    results = shader_plugins.register_configured()
    assert [r.ok for r in results] == [True]


def test_register_configured_empty_when_no_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect_config(monkeypatch, tmp_path)
    assert shader_plugins.register_configured() == []


def test_config_file_path_points_at_app_support_equivalent() -> None:
    p = shader_plugins.config_file_path()
    assert p.name == "shader_plugins.yaml"
    assert p.parent.name == "USDCheckerUI"
