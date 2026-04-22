"""Editor launcher — open a .usda file in VSCode at the line of a given prim.

Best-effort: we do not resolve sublayers or external references. If the prim
leaf name appears multiple (or zero) times in the .usda, we fall back to
line 1 and signal the ambiguity so the UI can show a toast.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


class EditorNotAvailableError(Exception):
    """Raised when the `code` CLI is not on PATH."""


class EditorLaunchFailedError(Exception):
    """Raised when `code` was resolved but launching it failed.

    Distinct from EditorNotAvailableError so the UI can react differently:
    missing CLI is a one-time installation prompt (QMessageBox); launch
    failure is a transient per-action glitch (status-bar toast).
    """


def resolve_vscode_path() -> str | None:
    # shutil.which consults PATHEXT on Windows, so it correctly resolves
    # `code` → `code.cmd`. The returned full path is what we feed Popen —
    # the bare string "code" would fail in Windows CreateProcess because
    # CreateProcess does NOT consult PATHEXT.
    return shutil.which("code")


def is_vscode_available() -> bool:
    return resolve_vscode_path() is not None


# Matches `def`, `over`, `class` declarations, with optional type token.
_DEF_LINE = re.compile(r'^\s*(?:def|over|class)\s+(?:\w+\s+)?"(?P<name>[^"]+)"')


def find_prim_line(usda_path: Path, prim_path: str) -> tuple[int, bool]:
    """Locate `def|over|class "<leaf>"` in `usda_path`.

    Returns (line_number, unambiguous). If the leaf name is missing or
    duplicated, returns (1, False) — caller is expected to show a toast.

    The regex parser can emit property-qualified paths like
    `/A/B/Shader.inputs:diffuseColor`; strip the `.attr[:prop]` tail
    before pulling the leaf prim name.
    """
    # Drop property / attribute suffix if present.
    plain_prim = prim_path.split(".", 1)[0]
    leaf = plain_prim.rstrip("/").rsplit("/", 1)[-1]
    if not leaf:
        return (1, False)

    matches: list[int] = []
    with usda_path.open("r", encoding="utf-8", errors="replace") as f:
        for idx, line in enumerate(f, start=1):
            m = _DEF_LINE.match(line)
            if m and m.group("name") == leaf:
                matches.append(idx)

    if len(matches) == 1:
        return (matches[0], True)
    return (1, False)


def open_in_vscode(file: Path, line: int | None) -> None:
    """Open `file` in VSCode at `line` (or line 1 if None)."""
    resolved = resolve_vscode_path()
    if resolved is None:
        raise EditorNotAvailableError("VSCode CLI `code` not found on PATH")
    target = f"{file}:{line or 1}:1"
    try:
        subprocess.Popen([resolved, "--goto", target])
    except OSError as exc:
        raise EditorLaunchFailedError(str(exc)) from exc
