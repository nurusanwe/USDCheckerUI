"""Plugins warmup — eager-load pxr so the first drag-drop doesn't race.

Called from __main__.main() BEFORE the Qt event loop starts. Forces pxr
plugin discovery and ComplianceChecker rule construction (~200 ms cost on
cold start).
"""

from __future__ import annotations


def warm() -> None:
    """Import pxr modules and instantiate a disposable ComplianceChecker."""
    from pxr import Ar, Sdf, Tf, Usd, UsdUtils  # noqa: F401 — intentional import-only

    _ = UsdUtils.ComplianceChecker()
