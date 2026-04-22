"""Diagnostic — immutable record for a single USD validation finding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "warning"]


@dataclass(slots=True, frozen=True)
class Diagnostic:
    """One validation finding produced by the runner.

    Frozen + slots makes instances hashable, picklable and safe to move
    across the QThread boundary without further copying.
    """

    rule: str
    severity: Severity
    message: str
    prim_path: str | None = None
    asset_path: str | None = None
    layer: str | None = None

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "prim_path": self.prim_path,
            "asset_path": self.asset_path,
            "layer": self.layer,
        }
