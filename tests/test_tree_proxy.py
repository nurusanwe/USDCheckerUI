"""Contract tests for the diagnostic tree proxy.

AC 12 pins `setRecursiveFilteringEnabled(True)` — verify it without
instantiating a QApplication (QSortFilterProxyModel doesn't need one).
"""
# ruff: noqa: I001  -- intentional import ordering around importorskip

from __future__ import annotations

import pytest

_ = pytest.importorskip("PySide6")

from usdchecker_ui.ui.diagnostic_tree import _RecursiveProxy  # noqa: E402


def test_recursive_filtering_enabled_on_proxy() -> None:
    proxy = _RecursiveProxy()
    assert proxy.isRecursiveFilteringEnabled() is True
