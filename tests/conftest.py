"""Shared pytest fixtures.

Heavy / binary fixtures (PNG texture, .usdz package) are built lazily from
text sources so the repo only commits text.
"""

from __future__ import annotations

# pxr import guard — MUST run before any test imports anything from pxr.
# If PYTHONPATH points at a hand-built USD install (common on dev boxes),
# it takes precedence over the venv's usd-core wheel and can segfault on
# ABI mismatch. We scrub any such path from sys.path at conftest load.
import contextlib as _contextlib
import sys as _sys
import sysconfig as _sysconfig
from pathlib import Path as _Path

# Anchors a sys.path entry must live under to survive the scrub. Using
# sysconfig is portable — the old substring heuristic matched
# "python3.12/lib", which never appears in Windows stdlib paths
# (C:\Python312\Lib), so the Windows stdlib got silently dropped.
_project_root = _Path(__file__).resolve().parents[1]
_venv_site = _sysconfig.get_paths().get("purelib")


def _keep_path(p: str) -> bool:
    if not p:
        return True
    try:
        resolved = _Path(p).resolve()
    except OSError:
        return False
    paths = _sysconfig.get_paths()
    anchors: list[_Path] = []
    for key in ("purelib", "stdlib", "platstdlib", "platlib"):
        raw = paths.get(key)
        if raw:
            try:
                anchors.append(_Path(raw).resolve())
            except OSError:
                continue
    with _contextlib.suppress(OSError):
        anchors.append(_project_root.resolve())
    for anchor in anchors:
        try:
            resolved.relative_to(anchor)
            return True
        except ValueError:
            continue
    return False


_sys.path[:] = [p for p in _sys.path if _keep_path(p)]
if _venv_site and _venv_site in _sys.path:
    _sys.path.remove(_venv_site)
    _sys.path.insert(0, _venv_site)

import base64  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
import yaml  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"

# Valid 1x1 red PNG (~68 bytes). Used by minimal_normalmap_invalid.usda so
# that NormalMapTextureChecker can resolve the texture file.
_RED_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlE"
    "QVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def red_png_path(fixtures_dir: Path) -> Path:
    """1x1 red PNG next to the .usda files so @red.png@ resolves."""
    target = fixtures_dir / "red.png"
    if not target.exists():
        target.write_bytes(base64.b64decode(_RED_PNG_B64))
    return target


@pytest.fixture(scope="session")
def valid_usda_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "minimal_valid.usda"


@pytest.fixture(scope="session")
def invalid_usda_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "minimal_invalid.usda"


@pytest.fixture(scope="session")
def normalmap_invalid_usda_path(fixtures_dir: Path, red_png_path: Path) -> Path:
    # red_png_path dependency ensures the texture is on disk before the
    # checker tries to resolve it.
    return fixtures_dir / "minimal_normalmap_invalid.usda"


@pytest.fixture(scope="session")
def usdz_path(fixtures_dir: Path, valid_usda_path: Path) -> Path:
    """Tiny valid .usdz built from minimal_valid.usda. Rebuilt on demand."""
    target = fixtures_dir / "minimal_package.usdz"
    if not target.exists():
        try:
            from pxr import UsdUtils
        except ImportError as exc:  # pragma: no cover
            pytest.skip(f"usd-core unavailable — cannot build .usdz fixture ({exc})")
        # CreateNewUsdzPackage zips + handles the 64B alignment for us.
        ok = UsdUtils.CreateNewUsdzPackage(str(valid_usda_path), str(target))
        if not ok:
            pytest.skip("CreateNewUsdzPackage returned False")
    return target


@pytest.fixture(scope="session")
def parser_samples(fixtures_dir: Path) -> list[dict]:
    with (fixtures_dir / "parser_samples.yaml").open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def large_corpus_path() -> Path:
    """Reads USDCHECKER_UI_TEST_CORPUS. Tests requesting this fixture skip if unset."""
    raw = os.environ.get("USDCHECKER_UI_TEST_CORPUS")
    if not raw:
        pytest.skip("USDCHECKER_UI_TEST_CORPUS not set — large corpus test skipped")
    path = Path(raw)
    if not path.exists():
        pytest.skip(f"USDCHECKER_UI_TEST_CORPUS points to missing file: {path}")
    return path
