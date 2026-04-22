# PyInstaller spec for USDChecker UI (Mac ARM, .app bundle).
#
# Run from repo root:
#     pyinstaller packaging/pyinstaller.spec --noconfirm
#
# Output: dist/USDCheckerUI.app
# Bundle size is not capped — measure post-build and report in README.

# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 — SPECPATH injected by PyInstaller

block_cipher = None

# usd-core's pxr package contains:
#   - compiled C extensions (pxr.Tf._tf, pxr.Sdf._sdf, ...) not picked up
#     by PyInstaller's static analysis
#   - native dylibs (libusd_*.dylib) that live alongside the .so modules
#   - plugin metadata (plugInfo.json + resources/) discovered at runtime by
#     the pxr PluginRegistry
# `collect_all` grabs all three categories in one call — the minimalist
# `hiddenimports=["pxr.Tf", ...]` approach loses the dylibs and plugInfos.
pxr_datas, pxr_binaries, pxr_hiddenimports = collect_all("pxr")

a = Analysis(  # noqa: F821
    [str(ROOT / "src" / "usdchecker_ui" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=pxr_binaries,
    datas=[
        (str(ROOT / "src" / "usdchecker_ui" / "core" / "patterns.yaml"),
         "usdchecker_ui/core"),
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
    console=False,
    disable_windowed_traceback=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=str(ROOT / "packaging" / "entitlements.plist"),
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

app = BUNDLE(  # noqa: F821
    coll,
    name="USDCheckerUI.app",
    icon=None,
    bundle_identifier="com.adobe.eclair.usdchecker-ui",
    info_plist={
        "CFBundleDisplayName": "USDChecker UI",
        "CFBundleName": "USDCheckerUI",
        "CFBundleIdentifier": "com.adobe.eclair.usdchecker-ui",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "13.0",
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "OpenUSD File",
                "CFBundleTypeRole": "Viewer",
                # Do NOT claim public.data — it makes the app shadow every
                # data-typed file on the system. Extensions alone suffice.
                "CFBundleTypeExtensions": ["usd", "usda", "usdc", "usdz"],
            }
        ],
    },
)
