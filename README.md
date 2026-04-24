# USDChecker UI

Desktop app (PySide6) that wraps OpenUSD validation and turns the raw
`usdchecker` output into human-readable diagnostics for artists and
pipeline devs. Validation is performed via the `usd-core` Python wheel
(same source as the official binary) — no subprocess, no dylib bundling.

Supported platforms: **macOS 13+ ARM, Windows 10+ x64.**

---

## Requirements

### macOS

- **Python 3.12** via Homebrew (`brew install python@3.12`) or pyenv.
  The macOS system Python (3.9) will NOT work.
- macOS 13+ on Apple Silicon.

### Windows

- **Python 3.12** (via `py -3.12`, the python.org installer, or
  `pyenv-win`).
- **Microsoft Visual C++ 2015–2022 Redistributable (x64)** on every
  target host. Install `vc_redist.x64.exe` from Microsoft. `usd-core`'s
  compiled modules link against `vcruntime140.dll` / `msvcp140.dll` /
  `vcomp140.dll`; without the redist the exe exits silently on launch
  (a traceback lands in `crash.log` — see the PYTHONPATH / crash-log
  section below).
- Windows 10+ x64.
- VSCode is optional — only used by the "Open in VSCode" toolbar action.

> **Shell note — PYTHONPATH.** If you have a hand-built USD install
> exposed via `PYTHONPATH` (common on USD-dev boxes), clear it
> in the shell you run USDChecker UI from. The venv's `usd-core` wheel
> must win so we link against a consistent ABI — otherwise you can get
> a segfault on `from pxr import Tf`. Tests scrub `sys.path` in
> `tests/conftest.py` so they work regardless. See the
> **PYTHONPATH diagnostic** subsection for an unambiguous `UNSET`/`SET`
> check in each shell.

---

## Dev install

### macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Windows

PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

cmd:

```cmd
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
pip install -e ".[dev]"
```

## Run the app (dev)

### macOS

```bash
unset PYTHONPATH       # if your shell sets it
python -m usdchecker_ui
```

### Windows

PowerShell:

```powershell
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
python -m usdchecker_ui
```

cmd:

```cmd
set PYTHONPATH=
python -m usdchecker_ui
```

Drop a `.usd / .usda / .usdc / .usdz` on the drop zone.

## Tests

### macOS

```bash
unset PYTHONPATH
pytest
```

### Windows

PowerShell:

```powershell
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
pytest
```

cmd:

```cmd
set PYTHONPATH=
pytest
```

### Optional large-corpus test

Point `USDCHECKER_UI_TEST_CORPUS` at a real `.usdz` on your disk (e.g.
`BMW.usdz`, ~631 MB). The corpus test skips automatically if the variable
is unset. **Never commit the corpus.**

```bash
export USDCHECKER_UI_TEST_CORPUS=/path/to/BMW.usdz
pytest tests/test_runner.py::test_large_corpus_smoke -v -s
```

### Lint + architecture contract

```bash
ruff check .
lint-imports      # enforces: core/ must not import PySide6/PyQt*
```

---

## Build

### macOS — Build `.app` (Mac ARM)

**Clean `build/` and `dist/` first** (`rm -rf build dist`) — stale
trees from a prior spec name can produce false positives.

```bash
pyinstaller packaging/pyinstaller.macos.spec --noconfirm
```

Artifact: `dist/USDCheckerUI.app`.

Bundle size (measured 2026-04-22 on Mac ARM, Python 3.12, PySide6 6.11,
usd-core 26.3): **~205 MB**. Dominated by `PySide6` + `usd-core` native
libs + pxr plugin metadata. No cap is enforced — if this creeps above
~350 MB later, consider `--exclude-module pxr.UsdImagingGL` / `pxr.Hgi*`
(rendering modules unused by the validator).

First launch after sharing the `.app` to someone else (quarantine attr):

```bash
xattr -d com.apple.quarantine USDCheckerUI.app
```

Apple signing / notarization is out of scope for the MVP.

### Windows — Build `.exe` (Win10+ x64)

**Clean `build\` and `dist\` first** (PowerShell:
`Remove-Item -Recurse -Force build, dist`; cmd: `rmdir /s /q build dist`)
— stale trees from the macOS spec can poison the Windows output.

Run from the repo root:

```powershell
pyinstaller packaging\pyinstaller.windows.spec --noconfirm
```

Artifact: `dist\USDCheckerUI\USDCheckerUI.exe` (one-folder layout; zip
`dist\USDCheckerUI\` to hand off).

**Icon.** A placeholder `USDCheckerUI.ico` ships in `packaging/`;
regenerate with `python packaging/_generate_ico.py` if the generator
changes (hash-pinned by `tests/test_ico_placeholder.py`).

**SmartScreen & Mark-of-the-Web (user-facing).** The exe is not
authenticode-signed, so on a clean Win10+ host:
- First launch pops SmartScreen ("Windows protected your PC"). Click
  **More info** → **Run anyway**. This is a one-time prompt per binary
  per user profile.
- Zipped downloads often carry Mark-of-the-Web. If the exe fails to
  launch and no traceback appears, right-click the zip (before
  extracting) → **Properties** → tick **Unblock** → extract.

**PYTHONPATH diagnostic (unambiguous).** Windows shells treat unset and
empty-string subtly differently; use an explicit idiom:
- cmd: `if defined PYTHONPATH (echo SET: %PYTHONPATH%) else (echo UNSET)`
- PowerShell: `if ($null -eq $env:PYTHONPATH) { 'UNSET' } else { "SET: $env:PYTHONPATH" }`

**Crash diagnostics.** If the exe exits on launch with no window, open
`%LOCALAPPDATA%\USDCheckerUI\crash.log` (PowerShell:
`notepad $env:LOCALAPPDATA\USDCheckerUI\crash.log`). A traceback
mentioning `pxr` / `Tf` with a foreign-looking path indicates
`PYTHONPATH` pollution; a `DLL load failed` / `vcruntime140` mention
indicates the VC++ 2015–2022 Redistributable is missing.

---

## Humanized explanations (`patterns.yaml`)

Explanations live in a layered YAML config:

- **Bundled default** — `src/usdchecker_ui/core/patterns.yaml` (read-only,
  shipped inside the `.app`).
- **User override** — `~/Library/Application Support/USDCheckerUI/patterns.yaml`
  on macOS, `%APPDATA%\USDCheckerUI\patterns.yaml` on Windows. Editable.
  Created on demand the first time you pick **Settings → Edit patterns…**
  in the app (it copies the bundled file).

User override wins rule-by-rule. **Settings → Reload patterns** re-enriches
the diagnostics currently on screen without re-running the USD check.

To add a new rule, append to the user file:

```yaml
- rule: SomeRuleNameFromUsdChecker
  title: Titre court affiché dans le panneau de détail
  explanation: |
    Contexte en langage humain — pourquoi le moteur a flagué ça.
  suggestion: |
    Piste de correction concrète.
```

---

## Shader plugin paths (renderer-specific shader definitions)

By default, USDChecker UI only knows about the shader types that ship
in the `usd-core` wheel — `UsdPreviewSurface`, `UsdUVTexture`,
`UsdTransform2d`, `UsdPrimvarReader_*`, and the MaterialX `ND_*`
library. Anything else (Adobe ASM, Houdini Karma, Renderman `Pxr*`,
in-house studio shaders) surfaces as **"Shader identifier not found
in Sdr registry"**, even though the shader is perfectly valid in the
pipeline that consumes the USD.

To make those shader types known during validation, register the
plugin directory that defines them via **Settings → Shader plugin
paths…**:

- **Add directory…** — pick a directory that contains a
  `plugInfo.json` directly (typical plugin layout).
- **Add plugInfo.json…** — pick the JSON file itself if it lives
  somewhere unusual.
- **Remove** — drops the path from the config. Note: pxr has no
  un-registration API, so removing only takes full effect on the
  next app launch.

The path list is persisted to:

- macOS   `~/Library/Application Support/USDCheckerUI/shader_plugins.yaml`
- Windows `%APPDATA%\USDCheckerUI\shader_plugins.yaml`

After adding a path, USDChecker UI re-validates the currently loaded
file automatically — the Sdr card should flip from "unknown" to a
clean diagnostic (or disappear entirely if the shader was the only
issue).

---

## Additional shader definitions (user-extensible)

If you hit the `Shader identifier not found in Sdr registry` error on
a shader family that is NOT already covered out of the box (Houdini
Karma shaders, Pixar RenderMan, an in-house studio renderer, …), you
can extend the known-shader set without rebuilding the app:

1. Find a `.usda` file that declares the shader identifiers your
   pipeline uses. This is typically shipped as part of the renderer
   install (`$HFS/houdini/.../*.usda`, `$RMANTREE/.../*.usda`, an
   internal studio .usda, etc.). It must contain one or more
   `def Shader "…" { info:id = "…" }` prims.
2. **Settings → Additional shader definitions…** → **Add .usda…** →
   pick the file.
3. The tool parses the file, extracts every `info:id` it declares,
   and unions those identifiers into the bundled set. The current
   file is re-validated automatically; matching "invalid shader node"
   diagnostics are suppressed on the next pass.

Under the hood this is the same mechanism that handles
`AdobeStandardMaterial_*` and the bundled MaterialX surface shaders —
you are extending the same suppression set. The user config is
persisted to:

- macOS   `~/Library/Application Support/USDCheckerUI/known_shader_sources.yaml`
- Windows `%APPDATA%\USDCheckerUI\known_shader_sources.yaml`

There is no public centralised registry of renderer shader
definitions; each vendor ships theirs with their install. Ask your
pipeline team where to find them if you are not sure.

---

## Built-in shader identifiers (zero-config)

USDChecker UI ships with a bundled `shader_definitions.usda` that
covers Adobe Standard Material out of the box. The file is parsed at
launch and the `info:id` values it declares
(`AdobeStandardMaterial_4_0`, `AdobeShadowCatchingMaterial_1_0`, …)
are treated as known. When the USD validator would otherwise emit
`Shader <…> has invalid shader node.` for a prim whose `info:id`
matches one of these identifiers, the diagnostic is silently
suppressed and a count is added to the status bar line so you can
see that something actually happened (e.g. "12 diagnostic(s) in
0.35s. — 3 known-shader warning(s) suppressed").

Why this is not done through pxr's Sdr plugin system
: the bundled shaders declare `info:implementationSource = "id"`
without any source asset / source code attached, which is the point
of that shader model. pxr's bundled Sdr parsers (glslfx, USD)
require a source they can parse to build an `SdrShaderNode`, so
they emit zero discovery results for these prims. On top of that,
pxr's Sdr plugin API is not usable from Python (`Sdr.DiscoveryPlugin`
cannot be subclassed from Python, `SetExtraDiscoveryPlugins` /
`SetExtraParserPlugins` only accept TfType references to C++
classes, and `AddDiscoveryResult` silently drops entries whose
`sourceType` no parser consumes). Suppressing the diagnostic in
the runner is therefore the only Python-only path that achieves a
zero-config experience; other renderer-specific shader types
(Houdini Karma, Renderman `Pxr*`, in-house studio shaders) remain
opt-in via Settings → Shader plugin paths…

The bundled `shader_definitions.usda` is a snapshot; it is not
fetched live. Refresh path: replace
`src/usdchecker_ui/core/bundled_shaders/shader_definitions.usda`
with an updated copy, commit, rebuild. Existing tests will tell
you if the set of declared identifiers changed.

---

## Manual smoke test (after build)

1. Launch the app (`.app` on macOS / `.exe` on Windows). Main window
   should appear within ~3s. On Windows, confirm the placeholder icon
   shows on the window title bar AND the taskbar entry (not the default
   Python/PyInstaller glyph).
2. Drag `tests/fixtures/minimal_invalid.usda` → diagnostic
   `ShaderPropertyTypeConformanceChecker` visible in the tree.
3. If `USDCHECKER_UI_TEST_CORPUS` points to a big `.usdz`, drag it —
   validation finishes without crash, diagnostics grouped by
   Severity → Rule → Prim.
4. Export → JSON → open in an editor → structure `{ meta: {...},
   diagnostics: [...] }` with `enrichment` either an object or `null`.
5. Settings → Edit patterns → tweak a `title` → Reload patterns → title
   on screen updates without re-running a check.
6. Open a `.usda` in VSCode (toolbar button). For `.usdz/.usd/.usdc`
   the button must be disabled with a tooltip. On Windows specifically:
   verify this works when `code` resolves to `code.cmd` (tests pin the
   Popen argv — see `tests/test_editor_launcher.py`).
7. Windows only — confirm `%LOCALAPPDATA%\USDCheckerUI\crash.log` does
   NOT exist after a clean launch-and-close cycle.

---

## Architecture — why the strict `core/` / `ui/` split?

`core/` is pure Python, **zero Qt**, enforced by `import-linter`. The
long-term plan is to port this validation layer to a C++ ImGUI
tool; keeping the core independent keeps that port
cheap. `tests/test_architecture.py` runs the contract on every CI run.
