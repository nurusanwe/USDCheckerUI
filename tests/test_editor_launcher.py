"""Tests for core.editor_launcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from usdchecker_ui.core import editor_launcher
from usdchecker_ui.core.editor_launcher import (
    EditorLaunchFailedError,
    EditorNotAvailableError,
    find_prim_line,
    is_vscode_available,
    open_in_vscode,
    resolve_vscode_path,
)


def test_is_vscode_available_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(editor_launcher.shutil, "which", lambda _name: "/usr/local/bin/code")
    assert is_vscode_available() is True


def test_is_vscode_available_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(editor_launcher.shutil, "which", lambda _name: None)
    assert is_vscode_available() is False


def test_find_prim_line_unique(valid_usda_path: Path) -> None:
    line, unambiguous = find_prim_line(valid_usda_path, "/World/Geom")
    assert unambiguous is True
    assert line >= 1


def test_find_prim_line_ambiguous(tmp_path: Path) -> None:
    forged = tmp_path / "dup.usda"
    forged.write_text(
        '#usda 1.0\n'
        'def Xform "World"\n'
        '{\n'
        '    def Scope "Duplicate" {}\n'
        '    def Xform "Nested" {\n'
        '        def Scope "Duplicate" {}\n'
        '    }\n'
        '}\n',
        encoding="utf-8",
    )
    line, unambiguous = find_prim_line(forged, "/World/Duplicate")
    assert unambiguous is False
    assert line == 1


def test_find_prim_line_missing(valid_usda_path: Path) -> None:
    line, unambiguous = find_prim_line(valid_usda_path, "/Nope")
    assert line == 1
    assert unambiguous is False


def test_find_prim_line_strips_property_suffix(valid_usda_path: Path) -> None:
    # Parser can emit property-qualified paths like `/A/B.inputs:x`; the
    # launcher must ignore everything after the first `.` to find the
    # actual prim def.
    line, unambiguous = find_prim_line(valid_usda_path, "/World/Geom.purpose")
    assert unambiguous is True
    assert line >= 1


def test_find_prim_line_accepts_over_and_class(tmp_path: Path) -> None:
    forged = tmp_path / "over_class.usda"
    forged.write_text(
        '#usda 1.0\n'
        'over "Taggy" {}\n'
        'class "Template" {}\n'
        'def Xform "Real" {}\n',
        encoding="utf-8",
    )
    line, unambiguous = find_prim_line(forged, "/Taggy")
    assert (line, unambiguous) == (2, True)
    line, unambiguous = find_prim_line(forged, "/Template")
    assert (line, unambiguous) == (3, True)


def test_open_in_vscode_raises_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(editor_launcher.shutil, "which", lambda _name: None)
    f = tmp_path / "x.usda"
    f.write_text("dummy", encoding="utf-8")
    with pytest.raises(EditorNotAvailableError):
        open_in_vscode(f, 1)


def test_resolve_vscode_path_returns_which_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(editor_launcher.shutil, "which", lambda _name: "/x/code")
    assert resolve_vscode_path() == "/x/code"
    monkeypatch.setattr(editor_launcher.shutil, "which", lambda _name: None)
    assert resolve_vscode_path() is None


def test_open_in_vscode_raises_launch_failed_on_popen_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(editor_launcher.shutil, "which", lambda _name: "/x/code")

    def _raise(*_args, **_kwargs):
        raise OSError("nope")

    monkeypatch.setattr(editor_launcher.subprocess, "Popen", _raise)
    f = tmp_path / "x.usda"
    f.write_text("dummy", encoding="utf-8")
    with pytest.raises(EditorLaunchFailedError) as excinfo:
        open_in_vscode(f, 1)
    assert "nope" in str(excinfo.value)


def test_open_in_vscode_passes_resolved_path_to_popen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # F12: Windows CreateProcess does NOT consult PATHEXT; bare "code" fails
    # on code.cmd. Passing the full resolved path (what shutil.which returns)
    # makes the launch work across platforms without shell=True.
    resolved = "/resolved/code.cmd"
    monkeypatch.setattr(editor_launcher.shutil, "which", lambda _name: resolved)

    captured: dict = {}

    def _fake_popen(argv, *args, **kwargs):
        captured["argv"] = argv
        return object()

    monkeypatch.setattr(editor_launcher.subprocess, "Popen", _fake_popen)

    f = tmp_path / "x.usda"
    f.write_text("dummy", encoding="utf-8")
    open_in_vscode(f, 1)

    assert captured["argv"] == [resolved, "--goto", f"{f}:1:1"]
