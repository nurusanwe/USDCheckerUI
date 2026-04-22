"""Shared pytest fixtures.

Heavy / binary fixtures (PNG texture, .usdz package) are built lazily from
text sources so the repo only commits text.
"""

from __future__ import annotations

# pxr import guard — MUST run before any test imports anything from pxr.
# If PYTHONPATH points at a hand-built USD install (common on dev boxes),
# it takes precedence over the venv's usd-core wheel and can segfault on
# ABI mismatch. We scrub any such path from sys.path at conftest load.
import sys as _sys
import sysconfig as _sysconfig

# Drop any sys.path entry that exposes a pxr package outside the venv —
# hand-built USD installs on dev boxes commonly leak in via PYTHONPATH and
# clash with usd-core's ABI, segfaulting the process. Explicit parens so
# the precedence is obvious and a falsy `_venv_site` can't empty sys.path.
_venv_site = _sysconfig.get_paths().get("purelib")
_project_root = str(__import__("pathlib").Path(__file__).resolve().parents[1])


def _keep_path(p: str) -> bool:
    if not p:
        return True
    if _venv_site and p.startswith(_venv_site):
        return True
    # Python stdlib + lib-dynload (framework paths).
    if "Python.framework" in p or "python3.12/lib" in p.replace("\\", "/"):
        return True
    # Project itself (src/ layout + repo root).
    return p == _project_root or p.startswith(_project_root + "/")


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
