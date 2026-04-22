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
> exposed via `PYTHONPATH` (common on Eclair / USD-dev boxes), clear it
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
long-term plan is to port this validation layer to an internal C++ ImGUI
tool (Eclair Studio); keeping the core independent keeps that port
cheap. `tests/test_architecture.py` runs the contract on every CI run.
