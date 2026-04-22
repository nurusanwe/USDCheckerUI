"""AC 15 — sys.excepthook writes a crash log.

The hook is installed in usdchecker_ui.__main__._install_crash_log.
Installing `__main__` pulls in PySide6 because __main__ imports the Qt
machinery at module top level — if PySide6 is unavailable we skip.
"""
# ruff: noqa: I001  -- intentional import ordering around importorskip

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ = pytest.importorskip("PySide6")

from usdchecker_ui import __main__ as app_main  # noqa: E402


def test_install_crash_log_writes_traceback_and_chains_previous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    crash_log = tmp_path / "USDCheckerUI" / "crash.log"
    monkeypatch.setattr(app_main, "_crash_log_path", lambda: crash_log)

    chained_calls: list[tuple] = []

    def _sentinel(exc_type, exc, tb):
        chained_calls.append((exc_type, str(exc)))

    # Install the sentinel as the "previous" hook, then install our
    # real hook on top. Restoring sys.excepthook is handled by
    # monkeypatch.
    monkeypatch.setattr(sys, "excepthook", _sentinel)
    app_main._install_crash_log()

    # Fabricate an exception with a real traceback.
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        sys.excepthook(type(exc), exc, exc.__traceback__)

    assert crash_log.exists()
    body = crash_log.read_text(encoding="utf-8")
    assert "RuntimeError" in body
    assert "boom" in body
    assert "Traceback" in body

    # Previous hook was called exactly once, with the same exception.
    assert len(chained_calls) == 1
    assert chained_calls[0] == (RuntimeError, "boom")


def test_install_crash_log_swallows_io_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If the log path can't be written (permissions / FS full), the hook
    # must NOT mask the original exception — it must still chain to the
    # previous hook.
    def _unwritable() -> Path:
        raise OSError("cannot compute path")

    monkeypatch.setattr(app_main, "_crash_log_path", _unwritable)

    chained_calls: list[tuple] = []

    def _sentinel(exc_type, exc, tb):
        chained_calls.append((exc_type, str(exc)))

    monkeypatch.setattr(sys, "excepthook", _sentinel)
    app_main._install_crash_log()

    try:
        raise ValueError("kaboom")
    except ValueError as exc:
        sys.excepthook(type(exc), exc, exc.__traceback__)

    assert chained_calls == [(ValueError, "kaboom")]


def test_crash_log_path_matches_current_platform() -> None:
    path = app_main._crash_log_path()
    assert path.name == "crash.log"
    assert path.parent.name == "USDCheckerUI"
    if sys.platform.startswith("win"):
        assert "USDCheckerUI" in str(path)
    elif sys.platform == "darwin":
        assert "Library" in path.parts
        assert "Logs" in path.parts
    else:
        assert ".local" in path.parts
        assert "state" in path.parts
