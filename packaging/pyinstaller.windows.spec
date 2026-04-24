# PyInstaller spec for USDChecker UI (Windows 10+ x64, one-folder exe).
#
# Run from repo root:
#     pyinstaller packaging\pyinstaller.windows.spec --noconfirm
#
# Output: dist\USDCheckerUI\USDCheckerUI.exe (+ sibling data files).
# Runtime prerequisite on the target host: Microsoft Visual C++ 2015–2022
# Redistributable (x64). usd-core's .pyd modules link against vcruntime140,
# msvcp140, vcomp140 — not bundled by collect_all("pxr").

# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 — SPECPATH injected by PyInstaller

block_cipher = None

# Same rationale as the macOS spec: collect_all pulls compiled .pyd + DLLs
# + plugInfo.json / resources in one call. The minimalist hiddenimports
# approach loses the native binaries and plugin metadata.
pxr_datas, pxr_binaries, pxr_hiddenimports = collect_all("pxr")

a = Analysis(  # noqa: F821
    [str(ROOT / "src" / "usdchecker_ui" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=pxr_binaries,
    datas=[
        (str(ROOT / "src" / "usdchecker_ui" / "core" / "patterns.yaml"),
         "usdchecker_ui/core"),
        (str(ROOT / "src" / "usdchecker_ui" / "core" / "bundled_shaders"
             / "shader_definitions.usda"),
         "usdchecker_ui/core/bundled_shaders"),
        *pxr_datas,
    ],
    hiddenimports=pxr_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="USDCheckerUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Release default. Python-level failures before Qt starts are captured
    # by the sys.excepthook installed in __main__.py (crash.log under
    # %LOCALAPPDATA%\USDCheckerUI\).
    console=False,
    disable_windowed_traceback=False,
    # No VSVersionInfo block in this iteration — future follow-up alongside
    # authenticode signing.
    version=None,
    icon=os.fspath((ROOT / "packaging" / "USDCheckerUI.ico").resolve()),
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="USDCheckerUI",
)
