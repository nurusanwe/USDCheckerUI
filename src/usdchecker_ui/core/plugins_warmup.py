"""Plugins warmup — eager-load pxr so the first drag-drop doesn't race.

Called from __main__.main() BEFORE the Qt event loop starts. Forces pxr
plugin discovery and ComplianceChecker rule construction (~200 ms cost on
cold start).

Why every schema submodule is imported:
    UsdSchemaRegistry::_InitializePrimDefsAndSchematicsForPluginSchemas()
    walks every plugInfo.json bundled in the wheel (UsdGeom, UsdLux,
    UsdPhysics, UsdSkel, UsdShade, …). For each schema it then looks up
    the matching TfType. TfTypes are registered lazily — by the
    TF_REGISTRY_FUNCTION blocks inside each _usd<Schema>.so — which
    only run once that module has been imported. Skip the import and
    you get a null TfType, which the registry dereferences and
    abort()s with Tf_PostNullSmartPtrDereferenceFatalError.

    The vanilla usd-core wheel happens to dodge this on the dev host
    because something else on the dev's Python path pulls the modules
    in early. A PyInstaller bundle built on a clean CI runner has no
    such side effect, so the abort reproduces there.

    Fix: import every schema module here, unconditionally. Cost is a
    one-off ~200 ms on cold start, already within the warmup budget.
"""

from __future__ import annotations

import importlib

# Every pxr schema package that ships a compiled _<name>.so in the
# usd-core wheel. Importing each one runs its TF_REGISTRY_FUNCTION
# bootstraps and registers the TfTypes the schema registry needs.
#
# Names match the Python sub-package names (camelCase after the Usd
# prefix), not the plugInfo keys.
_SCHEMA_MODULES = (
    "UsdGeom",
    "UsdHydra",
    "UsdLux",
    "UsdMedia",
    "UsdPhysics",
    "UsdProc",
    "UsdRender",
    "UsdRi",
    "UsdSemantics",
    "UsdShade",
    "UsdSkel",
    "UsdUI",
    "UsdValidation",
    "UsdVol",
)


def warm() -> None:
    """Import pxr base + schema modules and instantiate a disposable
    ComplianceChecker (which triggers UsdSchemaRegistry singleton init)."""
    # Base modules first — Tf/Plug/Sdf must be live before any schema
    # submodule registers into them.
    from pxr import Ar, Sdf, Tf, Usd, UsdUtils  # noqa: F401

    # Then every schema package, so its TfTypes are on the registry
    # before UsdSchemaRegistry starts walking plugInfos.
    for name in _SCHEMA_MODULES:
        importlib.import_module(f"pxr.{name}")

    # Finally, touch the ComplianceChecker. This is what drives
    # UsdSchemaRegistry singleton initialization; if any TfType were
    # still missing, this is where it would abort.
    _ = UsdUtils.ComplianceChecker()
