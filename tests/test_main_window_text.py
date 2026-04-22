"""Pinned AC 19 text — VSCode missing QMessageBox string.

Any edit that mangles quoting/typography in the message will break this test.
"""
# ruff: noqa: I001  -- intentional import ordering around importorskip

from __future__ import annotations

import pytest

_ = pytest.importorskip("PySide6")

from usdchecker_ui.ui.main_window import VSCODE_MISSING_TEXT  # noqa: E402


_AC19_EXACT = (
    "VSCode CLI (`code`) not found. Open VSCode → Cmd+Shift+P "
    "→ type 'Shell Command: Install \"code\" command in PATH' "
    "→ relaunch USDChecker UI."
)


def test_vscode_missing_text_matches_ac19_exact() -> None:
    assert VSCODE_MISSING_TEXT == _AC19_EXACT
