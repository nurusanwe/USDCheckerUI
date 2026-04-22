"""Regression gate for F13 — the `_keep_path` rewrite in tests/conftest.py.

The old implementation matched the substring `python3.12/lib`, which never
appears in Windows stdlib paths (`C:\\Python312\\Lib`) — so the scrub
silently dropped the Windows stdlib from `sys.path` and broke every test
on Windows.

The new implementation uses `sysconfig.get_paths()` anchors + subpath
check. These tests exercise the subpath logic against real directories
(`tmp_path`) so they run on every host. The AC 14 scenario with Windows
string literals is only meaningful on a Windows host — the equivalent
cross-platform guarantee is "any subpath of any reported sysconfig
anchor survives the scrub, anything else does not."
"""

from __future__ import annotations

import importlib.util
import sysconfig
from pathlib import Path

import pytest

_CONFTEST_PATH = Path(__file__).resolve().parent / "conftest.py"
_spec = importlib.util.spec_from_file_location("_usdchecker_conftest", _CONFTEST_PATH)
assert _spec is not None and _spec.loader is not None
_conftest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_conftest)


def _fake_paths(stdlib: Path, site: Path) -> dict[str, str]:
    return {
        "stdlib": str(stdlib),
        "platstdlib": str(stdlib),
        "purelib": str(site),
        "platlib": str(site),
    }


def test_keep_path_preserves_stdlib_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stdlib = tmp_path / "Python312" / "Lib"
    site = stdlib / "site-packages"
    site.mkdir(parents=True)

    monkeypatch.setattr(sysconfig, "get_paths", lambda: _fake_paths(stdlib, site))

    assert _conftest._keep_path(str(stdlib)) is True


def test_keep_path_preserves_site_packages_subpath(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stdlib = tmp_path / "Python312" / "Lib"
    site = stdlib / "site-packages"
    deep = site / "somepkg"
    deep.mkdir(parents=True)

    monkeypatch.setattr(sysconfig, "get_paths", lambda: _fake_paths(stdlib, site))

    assert _conftest._keep_path(str(deep)) is True


def test_keep_path_rejects_foreign_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stdlib = tmp_path / "Python312" / "Lib"
    site = stdlib / "site-packages"
    foreign = tmp_path / "foreign" / "usd" / "build" / "lib"
    site.mkdir(parents=True)
    foreign.mkdir(parents=True)

    monkeypatch.setattr(sysconfig, "get_paths", lambda: _fake_paths(stdlib, site))

    assert _conftest._keep_path(str(foreign)) is False


def test_keep_path_accepts_empty_string() -> None:
    # The empty entry in sys.path means "current directory" — legal and
    # should never be dropped by the scrub.
    assert _conftest._keep_path("") is True


def test_keep_path_tolerates_unresolvable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # OSError on resolve() must not crash the scrub — the path is
    # dropped defensively.
    class _BadPath(type(Path())):
        def resolve(self, *_args, **_kwargs):
            raise OSError("nope")

    # Swap the Path symbol used inside conftest for one that raises.
    monkeypatch.setattr(_conftest, "_Path", _BadPath)
    assert _conftest._keep_path("/anything") is False


def test_keep_path_with_real_current_sysconfig_anchors() -> None:
    # Cross-check: paths under the real test host's sysconfig anchors
    # survive the scrub. If this ever returns False for a site-packages
    # entry on a normal dev host, `_keep_path` is broken.
    paths = sysconfig.get_paths()
    for key in ("purelib", "stdlib"):
        raw = paths.get(key)
        if not raw:
            continue
        assert _conftest._keep_path(raw) is True
