"""Patterns store — layered YAML config (bundled default + user override).

User override wins rule-by-rule. Lives outside any signed bundle so it stays
editable post-install.
"""

from __future__ import annotations

import os
import subprocess
import sys
import warnings
from pathlib import Path

import yaml

from usdchecker_ui.core.enricher import PatternsDict


def _default_user_dir() -> Path:
    # Mac-first per spec. Use the platform-conventional user config dir on
    # others so the code doesn't silently write a "Library/Application
    # Support" tree on Linux/Windows test runners.
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "USDCheckerUI"
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home()))
        return base / "USDCheckerUI"
    return Path.home() / ".config" / "USDCheckerUI"


_BUNDLED_FILE = Path(__file__).with_name("patterns.yaml")
_USER_DIR = _default_user_dir()
_USER_FILE = _USER_DIR / "patterns.yaml"


def bundled_patterns_path() -> Path:
    return _BUNDLED_FILE


def user_patterns_path() -> Path:
    return _USER_FILE


def _load_yaml_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    if not isinstance(data, list):
        raise ValueError(f"patterns.yaml must be a YAML list at {path}")
    return data


def _as_index(entries: list[dict], source: str = "?") -> PatternsDict:
    """Group flat YAML entries by `rule` into ordered sub-pattern lists.

    Entries for the same rule are preserved in file order. The enricher
    relies on that order: specific `match:` substrings must come before
    any catch-all entry (one with no `match:` field) for the same rule.
    """
    out: PatternsDict = {}
    for entry in entries:
        rule = entry.get("rule") if isinstance(entry, dict) else None
        if not rule:
            warnings.warn(
                f"patterns.yaml ({source}) — entry without 'rule' key ignored: {entry!r}",
                stacklevel=2,
            )
            continue
        out.setdefault(rule, []).append({
            "match": entry.get("match"),
            "title": entry.get("title"),
            "explanation": entry.get("explanation"),
            "suggestion": entry.get("suggestion"),
        })
    return out


_USER_STUB = """# USDChecker UI — user override patterns.
#
# Override semantics:
#   - Overrides apply RULE BY RULE. If you list any entry for a given
#     rule here, it replaces ALL bundled entries for that rule. Rules
#     you don't list keep their bundled behavior.
#   - A rule can emit several distinct raw messages (e.g.
#     StageMetadataChecker flags missing upAxis, missing metersPerUnit,
#     missing defaultPrim, and non-Y upAxis — four different problems
#     with the same rule name). The optional `match:` field targets a
#     specific sub-case by matching a substring of the raw message.
#     List specific entries FIRST, end with a no-`match` catch-all.
#   - Order matters: the enricher walks your entries top-down and stops
#     at the first match.
#
# Template (copy, uncomment, tweak):
#
# - rule: StageMetadataChecker
#   match: "missing or invalid defaultPrim"
#   title: Scene has no default prim
#   explanation: |
#     Multi-line explanation targeting THIS specific sub-case.
#   suggestion: |
#     Concrete fix for THIS sub-case.
#
# - rule: StageMetadataChecker
#   # No `match` field = catch-all for this rule. Used when none of the
#   # specific entries above hit.
#   title: Stage metadata issue
#   explanation: |
#     Generic fallback explanation.
#   suggestion: |
#     Generic fix suggestion.

[]
"""


def ensure_user_override() -> Path:
    """Create an empty user-override file if missing.

    Idempotent — returns the user path either way. The stub is
    intentionally EMPTY (not a copy of the bundled file) so the user
    doesn't accidentally shadow future updates to the bundled defaults
    they never meant to override.
    """
    if not _USER_FILE.exists():
        _USER_DIR.mkdir(parents=True, exist_ok=True)
        _USER_FILE.write_text(_USER_STUB, encoding="utf-8")
    return _USER_FILE


def load_merged() -> PatternsDict:
    """Load bundled defaults, then overlay the user override rule-by-rule."""
    merged = _as_index(_load_yaml_list(_BUNDLED_FILE), source="bundled")
    if _USER_FILE.exists():
        merged.update(_as_index(_load_yaml_list(_USER_FILE), source="user"))
    return merged


def open_for_edit() -> Path:
    """Ensure the user override exists, then open it in the system editor."""
    path = ensure_user_override()
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    elif sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]  # Windows-only
    else:
        subprocess.Popen(["xdg-open", str(path)])
    return path


def reload() -> PatternsDict:
    """Re-read both layers and return a fresh merged dict."""
    return load_merged()
