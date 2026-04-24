"""Regression gate against mentions of the internal renderer code-name.

Per product policy the codebase must not reference the internal renderer
code-name in shipped artifacts (source, tests, docs, packaging config).
This test walks the repository and fails loudly if any occurrence
resurfaces — catches accidental re-introductions in future commits
(pull-request descriptions, code review, copy-paste from internal
docs, etc.)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Directories walked by the grep. Artefacts (build/, dist/, .venv/,
# caches, the bundled third-party .usda) are NOT scanned because their
# wording is out of our authorial control.
_SCANNED_ROOTS = (
    _REPO_ROOT / "src",
    _REPO_ROOT / "tests",
    _REPO_ROOT / "packaging",
    _REPO_ROOT / ".github",
)
_SCANNED_FILES = (
    _REPO_ROOT / "README.md",
    _REPO_ROOT / "pyproject.toml",
)

_SCANNED_SUFFIXES = {".py", ".yaml", ".yml", ".md", ".toml", ".spec", ".json"}

# Case-insensitive whole-word-ish match on the forbidden token. `re.IGNORECASE`
# catches Eclair / eclair / ECLAIR. Bounded on both sides by a non-alphanum
# so we don't match substrings of unrelated words (unlikely, but future-proof).
_FORBIDDEN = re.compile(r"(?<![A-Za-z0-9])eclair(?![A-Za-z0-9])", re.IGNORECASE)

# Explicit allow-list for FILES that are permitted to carry the token.
# The bundled shader_definitions.usda is pulled from an upstream public
# repository and has not historically used the token, but we pin the
# allow-list explicitly so any future drift is a conscious decision.
_ALLOWED_FILES = frozenset({
    _REPO_ROOT / "tests" / "test_no_eclair_mentions.py",
})


def _iter_candidate_files():
    seen: set[Path] = set()
    for root in _SCANNED_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix in _SCANNED_SUFFIXES:
                seen.add(p)
    for f in _SCANNED_FILES:
        if f.exists():
            seen.add(f)
    return sorted(seen)


def test_no_forbidden_mentions_in_shipped_artifacts() -> None:
    offending: list[str] = []
    for path in _iter_candidate_files():
        if path in _ALLOWED_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Binary content (.ico, committed screenshots) — skip.
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _FORBIDDEN.search(line):
                offending.append(f"{path.relative_to(_REPO_ROOT)}:{lineno}: {line.strip()}")
    assert not offending, (
        "Found mentions of the forbidden renderer code-name. Replace with "
        "neutral language (Adobe Standard Material, renderer-specific "
        "shaders, etc.):\n\n  " + "\n  ".join(offending)
    )


def test_allow_list_entries_exist() -> None:
    """The test file itself contains the token (in identifiers and in
    this docstring region) and must be present in the allow-list."""
    for allowed in _ALLOWED_FILES:
        assert allowed.exists(), f"allow-list points at missing file: {allowed}"
