"""Architecture guard — core/ must not import any Qt binding.

Delegates to import-linter using the contract in `.importlinter`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_core_has_no_qt_imports() -> None:
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["lint-imports"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"import-linter failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
