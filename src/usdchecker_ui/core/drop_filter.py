"""Pure helpers for filtering dropped files to the USD extensions we accept.

Qt-free by design so the rule is the same on every platform and can be
exercised by tests without instantiating a QApplication. UI widgets
(DropZone, MainWindow) extract the list of local file paths from their
Qt drop events and pass that list here.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

ACCEPTED_USD_EXTS: frozenset[str] = frozenset({".usd", ".usda", ".usdc", ".usdz"})


def first_accepted_file(local_file_paths: Iterable[str]) -> Path | None:
    """Return the first path whose suffix is in ACCEPTED_USD_EXTS.

    `local_file_paths` is expected to be what Qt's `QUrl.toLocalFile()`
    returned for each URL in a drop's mime data, already filtered to
    `QUrl.isLocalFile()` entries. Non-local URLs, empty strings, and
    paths with the wrong extension are skipped.

    Extension matching is case-insensitive (Windows Explorer often
    hands paths with uppercase extensions like `.USDA`).
    """
    for raw in local_file_paths:
        if not raw:
            continue
        path = Path(raw)
        if path.suffix.lower() in ACCEPTED_USD_EXTS:
            return path
    return None
