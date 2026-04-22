# USDChecker UI

Desktop app (PySide6) that wraps OpenUSD validation and turns the raw
`usdchecker` output into human-readable diagnostics for artists and
pipeline devs. Validation is performed via the `usd-core` Python wheel
(same source as the official binary) — no subprocess, no dylib bundling.

MVP target: **Mac ARM**. Windows build is on the roadmap.

---

## Requirements

- **Python 3.12** via Homebrew (`brew install python@3.12`) or pyenv.
  The macOS system Python (3.9) will NOT work.
- macOS 13+ on Apple Silicon.

> **Shell note — PYTHONPATH.** If you have a hand-built USD install exposed
> via `PYTHONPATH` (common on Eclair / USD-dev boxes), `unset PYTHONPATH`
> in the shell you run USDChecker UI from. The venv's `usd-core` wheel
> must win so we link against a consistent ABI — otherwise you can get
> a segfault on `from pxr import Tf`. Tests scrub `sys.path` in
> `tests/conftest.py` so they work regardless.

---

## Dev install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run the app (dev)

```bash
unset PYTHONPATH       # if your shell sets it
python -m usdchecker_ui
```

Drop a `.usd / .usda / .usdc / .usdz` on the drop zone.

## Tests

```bash
unset PYTHONPATH
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

## Build `.app` (Mac ARM)

```bash
pyinstaller packaging/pyinstaller.spec --noconfirm
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

---

## Humanized explanations (`patterns.yaml`)

Explanations live in a layered YAML config:

- **Bundled default** — `src/usdchecker_ui/core/patterns.yaml` (read-only,
  shipped inside the `.app`).
- **User override** — `~/Library/Application Support/USDCheckerUI/patterns.yaml`,
  editable. Created on demand the first time you pick
  **Settings → Edit patterns…** in the app (it copies the bundled file).

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

1. Launch the `.app`. Main window should appear within ~3s.
2. Drag `tests/fixtures/minimal_invalid.usda` → diagnostic
   `ShaderPropertyTypeConformanceChecker` visible in the tree.
3. If `USDCHECKER_UI_TEST_CORPUS` points to a big `.usdz`, drag it — validation
   finishes without crash, diagnostics grouped by Severity → Rule → Prim.
4. Export → JSON → open in an editor → structure `{ meta: {...},
   diagnostics: [...] }` with `enrichment` either an object or `null`.
5. Settings → Edit patterns → tweak a `title` → Reload patterns → title
   on screen updates without re-running a check.
6. Open a `.usda` in VSCode (toolbar button). For `.usdz/.usd/.usdc`
   the button must be disabled with a tooltip.

---

## Architecture — why the strict `core/` / `ui/` split?

`core/` is pure Python, **zero Qt**, enforced by `import-linter`. The
long-term plan is to port this validation layer to an internal C++ ImGUI
tool (Eclair Studio); keeping the core independent keeps that port
cheap. `tests/test_architecture.py` runs the contract on every CI run.
