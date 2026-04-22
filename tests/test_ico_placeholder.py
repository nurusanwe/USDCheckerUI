"""Hash-pin the committed placeholder ICO.

Two guarantees:

1. The bytes on disk at `packaging/USDCheckerUI.ico` match a SHA-256
   literal recorded here — so modifying `_generate_ico.py` (or swapping
   in an externally-authored ICO) requires a conscious acknowledgement
   by updating this hash.
2. Running the generator afresh produces byte-identical output — so
   the generator is reproducible, independent of interpreter patch
   version.

F2 (adversarial review): the pin is a SHA-256 literal, not a `git status`
check — the check is invariant to the developer's working tree state.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

_PACKAGING = Path(__file__).resolve().parents[1] / "packaging"
_COMMITTED_ICO = _PACKAGING / "USDCheckerUI.ico"
_GENERATOR = _PACKAGING / "_generate_ico.py"

# Computed from `python packaging/_generate_ico.py` on 2026-04-22.
# Update in the same commit as any generator change.
_EXPECTED_SHA256 = "bedbb99e007e3a1c3f23c76d835076f4d5f172dd80cdaf2124dc5186f791ad81"
_EXPECTED_SIZE = 9662  # 6 + 16 + 40 + 48*48*4 + 48*8


def _load_generator():
    # The generator lives outside the importable package tree; load it
    # by file path so we don't have to pollute sys.path.
    spec = importlib.util.spec_from_file_location("_generate_ico", _GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_ico_matches_hash() -> None:
    data = _COMMITTED_ICO.read_bytes()
    assert len(data) == _EXPECTED_SIZE
    assert hashlib.sha256(data).hexdigest() == _EXPECTED_SHA256


def test_generator_produces_identical_bytes(tmp_path: Path) -> None:
    gen = _load_generator()
    written = gen.generate(tmp_path)
    assert written.read_bytes() == _COMMITTED_ICO.read_bytes()
