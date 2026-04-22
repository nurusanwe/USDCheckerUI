"""Pinned AC 8 texts — VSCode missing QMessageBox string, per platform.

Any edit that mangles quoting / typography / case / arrow glyph in any of
the three branches of `_vscode_missing_text` will break this test.
"""
# ruff: noqa: I001  -- intentional import ordering around importorskip

from __future__ import annotations

import sys

import pytest

_ = pytest.importorskip("PySide6")

from usdchecker_ui.ui.main_window import (  # noqa: E402
    VSCODE_MISSING_TEXT,
    _vscode_missing_text,
)


# Byte-identical to the pre-spec AC 19 pin. Arrows are the RIGHTWARDS ARROW
# glyph (U+2192). A lookalike (e.g. U+279C HEAVY ROUND-TIPPED RIGHTWARDS
# ARROW) would change the bytes and fail the assertion.
_EXPECTED_DARWIN = (
    "VSCode CLI (`code`) not found. Open VSCode → Cmd+Shift+P "
    "→ type 'Shell Command: Install \"code\" command in PATH' "
    "→ relaunch USDChecker UI."
)

_EXPECTED_WIN = (
    "VSCode CLI (`code`) not found. Open VSCode → Ctrl+Shift+P "
    "→ type 'Shell: Install \"code\" command in PATH', or "
    "reinstall VSCode with 'Add to PATH' checked "
    "→ relaunch USDChecker UI."
)

_EXPECTED_OTHER = (
    "VSCode CLI (`code`) not found. Install VSCode and ensure `code` "
    "is on PATH, then relaunch USDChecker UI."
)


def test_darwin_text() -> None:
    result = _vscode_missing_text("darwin")
    assert result == _EXPECTED_DARWIN
    assert "Cmd+Shift+P" in result
    assert "Shell Command" in result


def test_windows_text() -> None:
    for token in ("win32", "win64"):
        result = _vscode_missing_text(token)
        assert result == _EXPECTED_WIN
        assert "Ctrl+Shift+P" in result
        assert "Add to PATH" in result
        assert "Cmd+Shift+P" not in result


def test_linux_text() -> None:
    result = _vscode_missing_text("linux")
    assert result == _EXPECTED_OTHER
    assert "VSCode" in result
    assert "PATH" in result
    assert "Cmd+Shift+P" not in result
    assert "Ctrl+Shift+P" not in result


def test_constant_matches_current_platform() -> None:
    # VSCODE_MISSING_TEXT is derived at import time from sys.platform;
    # keeps the constant honest even if the pure function grows new
    # branches.
    assert _vscode_missing_text(sys.platform) == VSCODE_MISSING_TEXT
