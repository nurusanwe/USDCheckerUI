---
title: 'USDChecker UI — Windows Support'
slug: 'windows-support'
created: '2026-04-22'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
adversarialReview:
  reviewedOn: '2026-04-22'
  findingsTotal: 22
  findingsIntegrated: 'F1, F2, F3, F5, F6, F7, F8, F9, F11, F12, F13, F15, F16, F18, F19, F20'
  findingsAckInNotes: 'F4, F10, F14, F17, F22'
  findingsDiscarded: 'F21 (noise — .usdz is gitignored + lazily built)'
tech_stack:
  - Python 3.12
  - PySide6 (Qt for Python, >= 6.7)
  - usd-core (PyPI wheel, pinned >=25.11,<27)
  - PyInstaller (>= 6.10)
  - PyYAML
files_to_modify:
  - packaging/pyinstaller.spec (rename → packaging/pyinstaller.macos.spec)
  - packaging/pyinstaller.windows.spec (new)
  - packaging/USDCheckerUI.ico (new, committed binary placeholder, 48×48)
  - packaging/_generate_ico.py (new, reproducibility script, layout fully pinned)
  - src/usdchecker_ui/__main__.py (install sys.excepthook crash-log on Windows)
  - src/usdchecker_ui/core/editor_launcher.py (EditorLaunchFailedError, resolved-path Popen, pure platform helper)
  - src/usdchecker_ui/ui/main_window.py (derive VSCODE_MISSING_TEXT via pure function, catch launch error)
  - tests/conftest.py (rewrite _keep_path to use sysconfig paths, not substring match)
  - tests/test_editor_launcher.py (cover EditorLaunchFailedError + Popen argv pinning)
  - tests/test_main_window_text.py (exercise all three platform branches via pure function)
  - tests/test_ico_placeholder.py (new, hash-pins the generated ICO + exercises the generator)
  - tests/test_conftest_keep_path.py (new, asserts scrub keeps Windows stdlib paths)
  - README.md (parallel macOS/Windows subsections, VC++ Redist requirement, SmartScreen + Icon + unambiguous PYTHONPATH check)
code_patterns:
  - 'core/ is Qt-free; enforced by import-linter contract `core-no-qt` (.importlinter)'
  - 'Typed exceptions defined in core/, caught at the UI boundary and surfaced via QMessageBox or a status-bar toast'
  - 'Platform branching via `sys.platform` (existing pattern in core/patterns_store.py: "darwin" / startswith("win") / else)'
  - 'Platform-dependent strings are produced by a PURE function taking the platform token as an argument; a module-level constant derives from `_fn(sys.platform)` so tests can exercise every branch independently of the current host (new pattern, introduced by this spec)'
  - 'Path handling uses pathlib.Path exclusively (no raw os.path concatenation in business code)'
  - 'PyInstaller spec uses `collect_all("pxr")` to pull native extensions, dylibs/DLLs, and plugInfo metadata in one call'
  - 'Global crash diagnostic: `sys.excepthook` is installed in `__main__.py` before Qt starts, writing a log to a platform-appropriate per-user directory; compensates for `console=False` on Windows (new pattern, introduced by this spec)'
test_patterns:
  - 'pytest with session-scoped fixtures in tests/conftest.py; heavy binaries (.usdz, .png) built lazily from text sources'
  - 'monkeypatch.setattr against module-level attributes (e.g. editor_launcher.shutil.which, editor_launcher.subprocess.Popen)'
  - 'pytest.importorskip("PySide6") guards tests that touch Qt types'
  - 'Pinned-string regression tests for critical UI copy (AC 19 pattern) — parametrized over all platform tokens the app ships for'
  - 'Hash-pinned assertions for committed binary assets (SHA-256 literal) — keeps generators honest across interpreter patch versions'
  - 'sys.path scrub in conftest.py uses sysconfig purelib/stdlib/platstdlib, NOT substring matching'
---

# Tech-Spec: USDChecker UI — Windows Support

**Created:** 2026-04-22

**Baseline commit:** `ca7482e` (Initial commit: USDChecker UI MVP (macOS))

**Adversarial review:** executed 2026-04-22. 22 findings; 16 integrated into
Tasks/ACs/Context, 5 acknowledged in Notes, 1 discarded as noise (F21:
`.usdz` is gitignored + lazily built by conftest, so fixture drift across
platforms is not a real concern).

## Overview

### Problem Statement

USDChecker UI currently ships only for macOS ARM. To distribute the app to
Windows users (QA, partner pipelines, external testers), we need:

1. A reproducible Windows build producing a standalone `.exe` that can be
   zipped and handed off, with no installer required.
2. The runtime (app + tests) to work cleanly on Windows 10+ x64, matching
   the Mac behavior.
3. Documentation for Windows users to mirror the existing macOS sections
   (install, run, test, build).

Several code and packaging paths are currently macOS-only, or are
subtly broken on Windows even when they look portable, and block this:

- The PyInstaller spec targets `arm64` and produces an `.app` bundle with
  `Info.plist` / entitlements.
- The README is entirely macOS-focused and mentions only the Mac-ARM MVP.
- The editor launcher's failure path is mac-flavored (the pinned "VSCode
  missing" message references `Cmd+Shift+P` and a macOS-only VSCode
  command), and `subprocess.Popen` has no try/except.
- **More severely, `subprocess.Popen(["code", ...])` on Windows fails
  outright even when `code.cmd` is on PATH** — Windows `CreateProcess`
  does not consult `PATHEXT`, so the bare string `"code"` cannot be
  resolved. `shutil.which("code")` works (it uses `PATHEXT`) but its
  return value is currently thrown away.
- **`tests/conftest.py`'s `_keep_path` heuristic matches the substring
  `"python3.12/lib"`** to preserve the stdlib — this never matches the
  Windows stdlib layout (`C:\Python312\Lib`, capital `L`, no `python3.12`
  segment), so the scrub would silently drop the entire stdlib from
  `sys.path` and break every test on Windows.
- **`console=False` on the Windows exe swallows startup errors** — any
  Python exception before Qt comes up (e.g. pxr ABI mismatch from a
  foreign `PYTHONPATH`) exits silently with no stderr, no log, no window.
  Without a crash-log path, AC 1 is un-diagnosable.

### Solution

- Add a Windows-specific PyInstaller spec (`packaging/pyinstaller.windows.spec`)
  producing a one-folder `.exe` at `dist/USDCheckerUI/USDCheckerUI.exe`;
  rename the existing spec to `packaging/pyinstaller.macos.spec` for
  symmetry.
- Harden `core/editor_launcher.py`: introduce `EditorLaunchFailedError`,
  wrap `subprocess.Popen` in `try/except OSError`, **and feed `Popen` the
  path returned by `shutil.which("code")` instead of the bare string
  `"code"` so `code.cmd` resolution works on Windows**.
- Refactor the VSCode-missing message out of a module-level constant into
  a **pure function** `_vscode_missing_text(platform: str) -> str` with
  three branches (darwin / win / fallback); `VSCODE_MISSING_TEXT` is
  still exported as `_vscode_missing_text(sys.platform)` so the import
  API stays identical, but tests can now exercise every branch on any
  host.
- Install a `sys.excepthook` in `__main__.py` that writes to a per-user
  log file (`%LOCALAPPDATA%\USDCheckerUI\crash.log` on Windows,
  `~/Library/Logs/USDCheckerUI/crash.log` on macOS), so `console=False`
  stays as the release default without blinding the first-run diagnosis.
- **Rewrite `tests/conftest.py`'s `_keep_path`** to compare against
  `sysconfig.get_paths()` entries (`purelib`, `stdlib`, `platstdlib`)
  instead of substring-matching a Mac-shaped path.
- Add a Windows section to `README.md` alongside the existing macOS
  content (PowerShell + cmd variants for install / run / test / build),
  **document the VC++ 2015–2022 Redistributable (x64) requirement**,
  **replace the ambiguous `echo %PYTHONPATH%` idiom** with a defined
  idiom, and cover SmartScreen first-run + Mark-of-the-Web.
- Ship a small reproducible `.ico` placeholder (**48×48 to keep the
  payload ~9 KB**, fully layout-pinned BMP-in-ICO) plus a stdlib-only
  generator; **pin the expected bytes via a SHA-256 literal in a test**
  rather than relying on `git status`.

### Scope

**In Scope:**
- New `packaging/pyinstaller.windows.spec` producing a one-folder Windows
  build (`dist/USDCheckerUI/USDCheckerUI.exe`). Uses `collect_all("pxr")`
  so pxr's native `.pyd` + DLLs + `plugInfo.json` are bundled.
- Rename `packaging/pyinstaller.spec` → `packaging/pyinstaller.macos.spec`
  (no content change); update README build instructions to reference both
  specs explicitly.
- Commit a **48×48 solid-color** `.ico` placeholder at
  `packaging/USDCheckerUI.ico` (~9 KB); `packaging/_generate_ico.py`
  writes a byte-identical file from a fully-pinned BMP-in-ICO layout
  documented in source comments: ICONDIR (6 B) + one ICONDIRENTRY (16 B)
  + BITMAPINFOHEADER (40 B, **bottom-up 32-bpp BGRA**, `biHeight =
  2 * SIZE` to include the AND-mask plane, `biSizeImage` set to the
  computed byte size) + color plane (no row padding needed at 32-bpp) +
  AND-mask (1-bpp, row-padded to 4 B). No PNG embedding. Pure stdlib.
- `core/editor_launcher.py`:
  - Add `EditorLaunchFailedError(Exception)`.
  - Change `is_vscode_available()` to stay boolean AND add
    `resolve_vscode_path() -> str | None` returning the `shutil.which`
    result so callers can use the resolved path.
  - In `open_in_vscode`, call `resolve_vscode_path()`; raise
    `EditorNotAvailableError` if `None`; otherwise call
    `subprocess.Popen([resolved_path, "--goto", target])` wrapped in
    `try/except OSError` and re-raise as `EditorLaunchFailedError`.
    **This fixes the Windows `code.cmd` invocation** (F12).
- `src/usdchecker_ui/__main__.py`:
  - Before `plugins_warmup.warm()`, install a `sys.excepthook` that
    appends exception text to a platform-appropriate per-user log:
    - Windows: `Path(os.environ.get("LOCALAPPDATA", Path.home())) / "USDCheckerUI" / "crash.log"`.
    - macOS: `Path.home() / "Library" / "Logs" / "USDCheckerUI" / "crash.log"`.
    - Other: `Path.home() / ".local" / "state" / "USDCheckerUI" / "crash.log"`.
  - The hook creates the parent directory (`mkdir(parents=True, exist_ok=True)`),
    appends timestamp + traceback, then calls the previous hook so the
    default stderr behavior (visible in dev) is preserved.
- `ui/main_window.py`:
  - Add a pure helper `_vscode_missing_text(platform: str) -> str` at
    module top level:
    - `platform == "darwin"` → current macOS string (byte-identical to the
      existing AC 19 pin, arrows encoded as `"→"` literals).
    - `platform.startswith("win")` → `"VSCode CLI (\`code\`) not found. Open
      VSCode → Ctrl+Shift+P → type 'Shell: Install ''code'' command
      in PATH', or reinstall VSCode with 'Add to PATH' checked →
      relaunch USDChecker UI."`.
    - else → `"VSCode CLI (\`code\`) not found. Install VSCode and ensure
      \`code\` is on PATH, then relaunch USDChecker UI."`.
  - `VSCODE_MISSING_TEXT = _vscode_missing_text(sys.platform)` at module
    import time — keeps the importable constant API (`from ... import
    VSCODE_MISSING_TEXT` remains valid).
  - `_on_editor_requested` catches `EditorLaunchFailedError` and shows a
    status-bar toast: `self._toast(f"VSCode launch failed: {exc}",
    duration_ms=6000)`. No `QMessageBox` on this path.
  - Add `import sys` at the top (currently not imported).
- `tests/conftest.py`:
  - **Rewrite `_keep_path`.** Keep a path `p` iff:
    - It is empty (no-op guard), OR
    - It equals or is a subpath of any of: `sysconfig.get_paths()["purelib"]`,
      `sysconfig.get_paths()["stdlib"]`, `sysconfig.get_paths()["platstdlib"]`,
      `sysconfig.get_paths()["platlib"]`, OR
    - It equals `_project_root` or starts with `_project_root + os.sep`.
  - Comparisons are done on `Path(p).resolve()` so symlinks and case
    normalization on Windows work. Drops the substring `"python3.12/lib"`
    and the `"Python.framework"` heuristic entirely.
- README changes (same file, sibling subsections under the existing
  headings; all items below are in scope and covered by AC 11):
  - "Requirements" → **macOS** + **Windows** subsections. Windows
    subsection lists Python 3.12 + **"Microsoft Visual C++ 2015–2022
    Redistributable (x64)"** as a mandatory prerequisite on the target
    host (install via `vc_redist.x64.exe` from Microsoft).
  - "Dev install" → macOS `source .venv/bin/activate` + Windows
    PowerShell (`.venv\Scripts\Activate.ps1`) and cmd
    (`.venv\Scripts\activate.bat`).
  - "Run the app (dev)" + "Tests" → Windows equivalents of
    `unset PYTHONPATH` (`Remove-Item Env:PYTHONPATH` in PowerShell or
    `set PYTHONPATH=` in cmd).
  - "Build" → separate subsections; Windows command references
    `pyinstaller.windows.spec`, artifact is
    `dist\USDCheckerUI\USDCheckerUI.exe`. Both subsections are prefixed
    with a one-line note: **"Always clean `build/` and `dist/` before
    invoking PyInstaller — stale trees from a prior spec name can
    produce false positives."**
  - Drop "MVP target: Mac ARM. Windows build is on the roadmap." —
    replaced by "Supported platforms: macOS 13+ ARM, Windows 10+ x64."
  - **Windows — SmartScreen note:** a dedicated paragraph covering
    (a) first-run SmartScreen prompt ("More info" → "Run anyway") in the
    absence of authenticode signing, and (b) Mark-of-the-Web on zipped
    downloads (Right-click → Properties → "Unblock" checkbox).
  - **Windows — Icon note:** one-liner under Build: "A placeholder
    `USDCheckerUI.ico` ships in `packaging/`; regenerate with
    `python packaging/_generate_ico.py`."
  - **PYTHONPATH pitfall (user-facing, Windows):** give a defined idiom
    so unset-vs-set is unambiguous:
    - cmd: `if defined PYTHONPATH (echo SET: %PYTHONPATH%) else (echo UNSET)`
    - PowerShell: `if ($null -eq $env:PYTHONPATH) { 'UNSET' } else { "SET: $env:PYTHONPATH" }`
  - Update the "Build `.app` (Mac ARM)" command to
    `pyinstaller packaging/pyinstaller.macos.spec --noconfirm`.

**Out of Scope:**
- Windows installer (MSI, NSIS, single-file self-extractor).
- Windows ARM64, Windows < 10, Windows Server SKUs.
- GitHub Actions (or any CI) for Windows.
- Authenticode signing / SmartScreen reputation.
- PyInstaller `VSVersionInfo` PE-metadata block (noted as a future
  iteration — easy to add alongside signing).
- Mac Intel, Linux.
- Designed icon artwork — the `.ico` is an intentional placeholder until
  a real asset is provided; macOS `.app` continues with `icon=None`
  (explicit decision, not oversight).
- New features, UI refactor, or behavior changes unrelated to portability.
- Dark-mode QA on Windows 11 beyond "Qt palette behaves reasonably";
  dedicated theming work is deferred.

## Context for Development

### Codebase Patterns

- **Strict `core/` / `ui/` split.** `core/` is pure Python and Qt-free,
  enforced by `import-linter` (`.importlinter`, contract `core-no-qt`).
  All new code in this spec keeps that contract: `EditorLaunchFailedError`
  and `resolve_vscode_path` live in `core/editor_launcher.py`; the UI
  toast lives in `ui/main_window.py`. `tests/test_architecture.py` runs
  the contract.
- **Platform branching idiom (existing, in `core/`).**
  `core/patterns_store.py` establishes the shape: `sys.platform ==
  "darwin"` → mac branch, `sys.platform.startswith("win")` → Windows
  branch, else → POSIX fallback.
- **Platform-dependent strings via a pure function (new, introduced
  here).** Platform strings are produced by a function taking the
  platform token as an argument; a module-level constant derives from
  `_fn(sys.platform)` when callers import by name. This is a new pattern
  in `ui/`, motivated by the test coverage gap identified in the
  adversarial review — it lets tests assert every branch on any host.
- **Typed-exception-at-boundary idiom.** `core/` raises typed exceptions
  (`EditorNotAvailableError`, `EditorLaunchFailedError`);
  `ui/main_window.py` catches each with a matched handler — `QMessageBox`
  for "missing CLI" (blocking), status-bar `_toast` for "launch failed"
  (non-blocking).
- **Global crash diagnostic (new, introduced here).**
  `src/usdchecker_ui/__main__.py` installs a `sys.excepthook` before
  `plugins_warmup.warm()` so any Python-level exception during import,
  warm-up, or Qt construction writes to a per-user log file. Required
  because `console=False` on the Windows exe suppresses stderr. The
  previous hook is chained so dev stderr output is preserved.
- **Path handling via `pathlib.Path`** everywhere in business code. No
  raw `os.path.join` or string concatenation for paths. Spec files
  resolve explicitly: `os.fspath((ROOT / "packaging" / "USDCheckerUI.ico").resolve())`
  so the path passed to PyInstaller is absolute and
  platform-normalized.
- **PyInstaller `collect_all("pxr")`** is the established strategy; the
  Windows spec reuses it verbatim. The minimalist `hiddenimports=[...]`
  alternative is not used because it misses native `.dylib` / `.dll` and
  `plugInfo.json`.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `packaging/pyinstaller.spec` | Source of the `collect_all("pxr")` recipe, pxr data/binary plumbing, `EXE`/`COLLECT`/`BUNDLE` structure. Rename target. |
| `packaging/entitlements.plist` | macOS-only, unchanged in this spec (referenced only by the renamed macOS spec). |
| `packaging/Info.plist.template` | macOS-only, unchanged. |
| `src/usdchecker_ui/__main__.py` | Entry point; gains a `sys.excepthook` install before `plugins_warmup.warm()`. |
| `src/usdchecker_ui/core/editor_launcher.py` | Home of `EditorNotAvailableError`, `is_vscode_available`, `open_in_vscode`; gains `EditorLaunchFailedError`, `resolve_vscode_path`, and the resolved-path `Popen` call. |
| `src/usdchecker_ui/ui/main_window.py` | Where `VSCODE_MISSING_TEXT` is defined (lines 29–33); gains `_vscode_missing_text(platform)` and a launch-failure toast branch in `_on_editor_requested` (lines 183–204). Needs `import sys` added. |
| `src/usdchecker_ui/core/patterns_store.py` | Reference implementation of the `sys.platform` branching idiom. |
| `tests/conftest.py` | `_keep_path` heuristic is rewritten to use `sysconfig.get_paths()` entries; the current substring-match approach would drop the Windows stdlib from `sys.path`. |
| `tests/test_editor_launcher.py` | Existing pattern for `monkeypatch.setattr(editor_launcher.shutil, "which", ...)`. New tests cover `EditorLaunchFailedError` and pin the `Popen` argv to include the resolved path. |
| `tests/test_main_window_text.py` | Pins the AC 19 text; becomes parametrized over every platform token the app ships for. |
| `tests/test_ico_placeholder.py` | New test file. Hash-pins `packaging/USDCheckerUI.ico` against a SHA-256 literal; runs `_generate_ico.py` and asserts byte equality. |
| `tests/test_conftest_keep_path.py` | New test file. Asserts `_keep_path` preserves Windows-shaped stdlib paths by stubbing `sysconfig.get_paths()`. |
| `.importlinter` | Contract that forbids `PySide6`/`PyQt*` imports in `usdchecker_ui.core`. Do not weaken. |
| `README.md` | Single source of truth for dev-install / run / test / build; receives the Windows subsections, VC++ Redist requirement, SmartScreen note, Icon note, and unambiguous PYTHONPATH idiom. |

### Technical Decisions

- **Two PyInstaller specs, not one conditional spec.** Each spec stays
  linear and readable; README commands are explicit
  (`pyinstaller packaging/pyinstaller.macos.spec` vs `...windows.spec`).
  Sharing the `collect_all("pxr")` recipe is 3 lines of duplication —
  acceptable.
- **Icon is Windows-only in this spec.** macOS bundle continues with
  `icon=None` until a real `.icns` asset lands (macOS ignores `.ico`);
  this is an explicit decision, not oversight.
- **`.ico` placeholder = 48×48, fully pinned BMP-in-ICO, hash-tested.**
  Size 48×48 @ 32-bpp gives ~9 KB vs the naïve 256×256 (~256 KB). Layout
  is documented in `_generate_ico.py` module-docstring and comments:
  ICONDIR + one ICONDIRENTRY + BITMAPINFOHEADER (bottom-up, 32-bpp BGRA,
  `biHeight = 2*SIZE` for XOR+AND planes, `biSizeImage` computed
  explicitly) + XOR plane + AND mask (1-bpp, row-padded to 4 B, all
  zeros). AC 4 asserts a SHA-256 hash literal, not `git status` — so
  the check is invariant to interpreter patch versions and to the
  developer's working tree state.
- **VSCode-missing message is a pure function; the constant is derived.**
  `_vscode_missing_text(platform: str) -> str` is the source of truth;
  `VSCODE_MISSING_TEXT = _vscode_missing_text(sys.platform)` preserves
  the existing import API. Unicode arrows are encoded as `"→"`
  escapes in the source so typography can never drift into lookalike
  glyphs on copy-paste.
- **Editor launcher passes the resolved `which()` path to `Popen` —
  the one "heroic" we accept.** Windows `CreateProcess` does not consult
  `PATHEXT`, so `Popen(["code", ...])` fails on `code.cmd` even when
  `shutil.which("code")` returns it. Using the resolved path
  (`Popen([resolved, "--goto", target])`) fixes this for free on every
  platform; no `shell=True`. The "best-effort" posture is preserved —
  if `Popen` still fails, `EditorLaunchFailedError` surfaces a toast.
  `except OSError` alone is sufficient (`FileNotFoundError` is an
  `OSError`); we do not wrap `SubprocessError` / `ValueError` because
  our argv is well-formed and not user-supplied.
- **`console=False` + crash-log excepthook.** Release Windows build
  stays windowless (no flashing console). Any Python-level exception
  before Qt is up goes to `%LOCALAPPDATA%\USDCheckerUI\crash.log`.
  During dev, the hook chain preserves default stderr so a console
  run (`python -m usdchecker_ui`) still shows tracebacks inline.
- **`conftest.py` scrub uses `sysconfig`, not substrings.**
  Heuristic-by-substring is not portable: the Mac-shaped
  `"python3.12/lib"` token does not appear in Windows paths
  (`C:\Python312\Lib`). Rewrite compares `Path(p).resolve()` against
  `sysconfig.get_paths()`'s `purelib`, `stdlib`, `platstdlib`,
  `platlib` values. Case-insensitive matching on Windows is handled
  by `Path.resolve()`.
- **PYTHONPATH scrub is doc-only for the shipped exe.** The runtime
  scrub in `conftest.py` is test-only. The shipped exe does not mutate
  a user's environment; the README explains the defined unambiguous
  idiom to diagnose (`if defined PYTHONPATH (...)`, `if ($null -eq
  $env:PYTHONPATH)...`) and the crash-log path for post-mortem.
- **"Deferred AC" is abolished; Windows ACs are blocking for handoff.**
  The prior wording allowed AC 1 / AC 3 / AC 9 to be marked "deferred"
  when a Windows host was unavailable. That created a category of
  spec-complete-but-unverified deliverables. The replacement rule:
  **no Windows binary may be handed off to any user until AC 1, AC 3,
  AC 9 have been verified on a real Win10+ x64 host**; if the
  implementation PR lands ahead of that verification, it must be
  flagged as internal-only in the commit body and the handoff is
  gated on a follow-up verification note.
- **No installer in scope.** One-folder `.exe` + zip-and-ship is the
  entire delivery model for this iteration.

## Implementation Plan

### Tasks

Ordered by dependency (each task is a discrete, committable unit).

- [ ] **Task 1: Rename the macOS PyInstaller spec.**
  - File: `packaging/pyinstaller.spec` → `packaging/pyinstaller.macos.spec`
  - Action: `git mv` only. No content change.
  - Notes: Symmetry step that unblocks README updates and clarifies the
    Windows spec's identity.

- [ ] **Task 2: Add the ICO generator script.**
  - File: `packaging/_generate_ico.py` (new)
  - Action: Stdlib-only script (`struct`, `pathlib`, `sys`) writing
    `packaging/USDCheckerUI.ico` from fully-pinned constants at module
    scope:
    - `SIZE = 48`
    - `BGRA = (180, 100, 30, 255)` (Eclair-ish blue; stored in BGRA
      because BMP DIB is BGRA, not RGBA)
  - Layout, documented in the module docstring:
    - ICONDIR (6 B): `reserved=0, type=1 (ICO), count=1`.
    - ICONDIRENTRY (16 B): `width=48, height=48, colors=0, reserved=0,
      planes=1, bit_count=32, bytes_in_res=<computed>, image_offset=22`.
    - BITMAPINFOHEADER (40 B): `biSize=40, biWidth=48,
      biHeight=96 (=2*SIZE, XOR+AND planes), biPlanes=1,
      biBitCount=32, biCompression=0 (BI_RGB), biSizeImage=<XOR bytes
      + AND bytes>, biX/YPelsPerMeter=0, biClrUsed=0,
      biClrImportant=0`.
    - XOR plane: `SIZE * SIZE` pixels × 4 B BGRA, bottom-up row order
      (last row first). At 32-bpp, no row padding needed (row size
      already multiple of 4).
    - AND mask: `SIZE` rows × `ceil(SIZE/8) padded to multiple of 4` B,
      all zeros (transparency-by-zero).
  - Script entry point: when run as `__main__`, write the file next to
    itself (`Path(__file__).parent / "USDCheckerUI.ico"`) and print the
    byte count + SHA-256.
  - Idempotent: same output every run, verifiable by the AC 4 hash.
  - Notes: No Pillow. No PNG. Docstring pins the exact layout so a
    reader can audit the format without running the script.

- [ ] **Task 3: Generate and commit the placeholder ICO.**
  - File: `packaging/USDCheckerUI.ico` (new, binary, ~9 KB expected:
    6 + 16 + 40 + 48×48×4 + 48×ceil(48/8→8) = 62 + 9216 + 384 = 9662 B)
  - Action: Run `python packaging/_generate_ico.py` from repo root;
    `git add packaging/USDCheckerUI.ico`. Note the SHA-256 printed by
    the script; paste it into Task 12 as the pinned hash.
  - Notes: Commit alongside Task 2 so builds don't need a pre-step.

- [ ] **Task 4: Create the Windows PyInstaller spec.**
  - File: `packaging/pyinstaller.windows.spec` (new)
  - Action: Copy structure from the renamed macOS spec, keep
    `collect_all("pxr")`, `pathex`, `datas` (including `patterns.yaml`),
    and `hiddenimports`. Differences:
    - Drop `target_arch` and `entitlements_file` from `EXE(...)`.
    - Set `icon=os.fspath((ROOT / "packaging" / "USDCheckerUI.ico").resolve())`
      on `EXE(...)`. Import `os` at the top.
    - Keep `console=False` (release default; crash log covers it via
      Task 5).
    - Set `version=None` (no `VSVersionInfo` in this iteration; see
      Notes → Future iterations for the follow-up).
    - Drop the `BUNDLE(...)` call entirely — no `.app` equivalent.
    - Keep `COLLECT(...)` with `name="USDCheckerUI"` so the one-folder
      output is `dist/USDCheckerUI/`.
  - README preamble (in Task 11) must say "run from repo root" so
    `SPECPATH` resolution is deterministic.
  - Notes: Produces `dist/USDCheckerUI/USDCheckerUI.exe` + sibling
    files.

- [ ] **Task 5: Install the crash-log `sys.excepthook` in `__main__`.**
  - File: `src/usdchecker_ui/__main__.py`
  - Action:
    - Add `import os`, `import traceback`, `import datetime as _dt`.
    - Define `_crash_log_path() -> Path`:
      - Windows: `Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        / "USDCheckerUI" / "crash.log"`.
      - macOS: `Path.home() / "Library" / "Logs" / "USDCheckerUI" / "crash.log"`.
      - else: `Path.home() / ".local" / "state" / "USDCheckerUI" / "crash.log"`.
    - Define `_install_crash_log()`:
      - Capture `previous = sys.excepthook`.
      - Define `hook(exc_type, exc, tb)`:
        - Build log dir via `path.parent.mkdir(parents=True, exist_ok=True)`.
        - Append one line `"[<iso-timestamp>] <exc_type.__name__>: <exc>"` +
          `"".join(traceback.format_exception(exc_type, exc, tb))`.
        - Call `previous(exc_type, exc, tb)` so dev stderr is
          preserved.
      - Swallow any I/O error inside the hook (never mask the original
        exception).
      - Assign `sys.excepthook = hook`.
    - Call `_install_crash_log()` at the top of `main()`, before
      `plugins_warmup.warm()`.
  - Notes: `import sys` is already present (line 5). This is the sole
    I/O side-effect before Qt — keep it trivial and unconditional.

- [ ] **Task 6: Extend `core/editor_launcher.py`.**
  - File: `src/usdchecker_ui/core/editor_launcher.py`
  - Action:
    - Add class `EditorLaunchFailedError(Exception)` below
      `EditorNotAvailableError`.
    - Add module-level `def resolve_vscode_path() -> str | None: return
      shutil.which("code")`.
    - Leave `is_vscode_available()` as-is (boolean wrapper).
    - Rewrite `open_in_vscode`:
      - `resolved = resolve_vscode_path()`
      - `if resolved is None: raise EditorNotAvailableError("VSCode CLI
        `code` not found on PATH")`
      - `target = f"{file}:{line or 1}:1"`
      - `try: subprocess.Popen([resolved, "--goto", target])`
      - `except OSError as exc: raise EditorLaunchFailedError(str(exc))
        from exc`
    - `EditorNotAvailableError` raising path is unchanged semantically;
      only the message is pinned.
  - Notes: No PySide6 import; `core-no-qt` intact. The resolved-path
    change is the fix for F12 — `code.cmd` on Windows now works.

- [ ] **Task 7: Make `VSCODE_MISSING_TEXT` testable on any platform.**
  - File: `src/usdchecker_ui/ui/main_window.py`
  - Action:
    - **Add** `import sys` at the top (not currently imported).
    - Add a module-level pure function
      `_vscode_missing_text(platform: str) -> str` above the current
      constant definition:
      - `if platform == "darwin"`: return the current macOS string,
        encoding arrows as `"→"` literals — **byte-identical to
        the existing pin**.
      - `elif platform.startswith("win")`: return a Windows-flavored
        string containing `"Ctrl+Shift+P"` and `"Add to PATH"` and the
        word `"VSCode"`.
      - `else`: return a generic fallback containing `"VSCode"`,
        `"code"`, and `"PATH"`.
    - Define `VSCODE_MISSING_TEXT = _vscode_missing_text(sys.platform)`.
      Keep the name exported so existing imports still work.
    - In `_on_editor_requested`, add
      `except editor_launcher.EditorLaunchFailedError as exc: self._toast(f"VSCode launch failed: {exc}", duration_ms=6000)`
      after the existing `EditorNotAvailableError` handler.
  - Notes: The function is the source of truth; the constant is a
    convenience. Tests call the function with each platform token —
    AC 8 is now testable on any host.

- [ ] **Task 8: Cover the new launch-failure path and pin the argv.**
  - File: `tests/test_editor_launcher.py`
  - Action:
    - Import `EditorLaunchFailedError` and `resolve_vscode_path` from
      `usdchecker_ui.core.editor_launcher`.
    - Add `test_open_in_vscode_raises_launch_failed_on_popen_error`:
      monkeypatch `shutil.which` → `"/some/code"`; monkeypatch
      `subprocess.Popen` → callable raising `OSError("nope")`; assert
      `pytest.raises(EditorLaunchFailedError)` with `"nope"` in the
      message.
    - Add `test_open_in_vscode_passes_resolved_path_to_popen`:
      monkeypatch `shutil.which` → `"/resolved/code.cmd"`; monkeypatch
      `subprocess.Popen` to capture its argv; call `open_in_vscode` and
      assert `argv == ["/resolved/code.cmd", "--goto",
      f"{file}:1:1"]` — pins F12's fix.
  - Notes: Follows the existing `monkeypatch.setattr(editor_launcher.shutil,
    "which", ...)` pattern.

- [ ] **Task 9: Make the pinned-text test exercise all platforms.**
  - File: `tests/test_main_window_text.py`
  - Action:
    - Import `_vscode_missing_text` (module-private but test-visible)
      and `VSCODE_MISSING_TEXT` from `usdchecker_ui.ui.main_window`.
    - Define three expected strings:
      `_EXPECTED_DARWIN`, `_EXPECTED_WIN`, `_EXPECTED_OTHER` — each a
      byte-literal pin. `_EXPECTED_DARWIN` equals the current AC 19
      string (arrows as `"→"`).
    - `test_darwin_text`: `assert _vscode_missing_text("darwin") == _EXPECTED_DARWIN`.
    - `test_windows_text`: `assert _vscode_missing_text("win32") == _EXPECTED_WIN`
      and `"Ctrl+Shift+P" in result` and `"Cmd+Shift+P" not in result`.
    - `test_linux_text`: `assert _vscode_missing_text("linux") == _EXPECTED_OTHER`
      and `"Cmd+Shift+P" not in result` and `"Ctrl+Shift+P" not in result`.
    - `test_constant_matches_current_platform`: `assert VSCODE_MISSING_TEXT
      == _vscode_missing_text(sys.platform)` — keeps the import-time
      derivation honest.
  - Notes: These run on any OS and give real coverage for all three
    branches. Replaces the single-string pin.

- [ ] **Task 10: Rewrite `conftest.py` `_keep_path` to use `sysconfig`.**
  - File: `tests/conftest.py`
  - Action:
    - Replace the current `_keep_path` body with a function that
      resolves both `p` and the sysconfig paths, then checks subpath
      membership:
      ```python
      def _keep_path(p: str) -> bool:
          if not p:
              return True
          try:
              resolved = Path(p).resolve()
          except OSError:
              return False
          paths = sysconfig.get_paths()
          anchors = [paths.get(k) for k in ("purelib", "stdlib", "platstdlib", "platlib")]
          anchors = [Path(a).resolve() for a in anchors if a]
          anchors.append(Path(_project_root).resolve())
          for anchor in anchors:
              try:
                  resolved.relative_to(anchor)
                  return True
              except ValueError:
                  continue
          return False
      ```
    - Drop `Python.framework`, `python3.12/lib`, `_venv_site` string
      logic. Keep the existing `_venv_site` variable only for the
      "insert at front" step after filtering (or compute fresh via
      `sysconfig.get_paths()["purelib"]`).
  - Notes: This is the only spec change to a test scaffolding file. It
    also happens to make macOS stdlib detection more robust (no reliance
    on `Python.framework` substring).

- [ ] **Task 11: Update `README.md` with Windows subsections + adversarial-review asks.**
  - File: `README.md`
  - Action (all items are in AC 11):
    - Replace "MVP target: Mac ARM. Windows build is on the roadmap."
      with "Supported platforms: macOS 13+ ARM, Windows 10+ x64."
    - Split each of "Requirements", "Dev install", "Run the app (dev)",
      "Tests", and "Build" into parallel `### macOS` and `### Windows`
      subsections.
    - **Windows — Requirements:** Python 3.12; **Microsoft Visual C++
      2015–2022 Redistributable (x64)** (one-sentence link to
      Microsoft's `vc_redist.x64.exe`); VSCode optional (best-effort
      "Open in VSCode"); Windows 10+ x64.
    - **Windows — Dev install:** `py -3.12 -m venv .venv` +
      `.venv\Scripts\Activate.ps1` (PowerShell) /
      `.venv\Scripts\activate.bat` (cmd) + `pip install -e ".[dev]"`.
    - **Windows — Run:** `Remove-Item Env:PYTHONPATH` (PS) or
      `set PYTHONPATH=` (cmd), then `python -m usdchecker_ui`.
    - **Windows — Tests:** same env-clear + `pytest`.
    - **Windows — Build:** prefix with "**Clean `build\\` and `dist\\`
      first** (`Remove-Item -Recurse -Force build, dist` in PS); then
      `pyinstaller packaging\pyinstaller.windows.spec --noconfirm` from
      the repo root; artifact `dist\USDCheckerUI\USDCheckerUI.exe`."
    - **Windows — SmartScreen / Mark-of-the-Web (user-facing):**
      dedicated paragraph covering the first-run SmartScreen prompt
      (unsigned; click "More info" → "Run anyway") and zipped-download
      MOTW (Right-click → Properties → "Unblock").
    - **Windows — PYTHONPATH pitfall (user-facing, unambiguous idiom):**
      - cmd: `if defined PYTHONPATH (echo SET: %PYTHONPATH%) else (echo UNSET)`
      - PowerShell: `if ($null -eq $env:PYTHONPATH) { 'UNSET' } else { "SET: $env:PYTHONPATH" }`
      - Plus the diagnostic flow: "If the exe crashes on launch and no
        window appears, look at `%LOCALAPPDATA%\USDCheckerUI\crash.log`
        (PS: `notepad $env:LOCALAPPDATA\USDCheckerUI\crash.log`). A
        traceback mentioning `pxr`/`Tf` with a foreign-looking path
        indicates `PYTHONPATH` pollution."
    - **Windows — Icon:** one-liner under Build: "A placeholder
      `USDCheckerUI.ico` ships in `packaging/`; regenerate with
      `python packaging/_generate_ico.py`."
    - **macOS — Build:** prefix with "**Clean `build/` and `dist/`
      first** (`rm -rf build dist`); then
      `pyinstaller packaging/pyinstaller.macos.spec --noconfirm`."
  - Notes: Keep the existing "Architecture — core/ui split" section
    untouched; it is still accurate.

- [ ] **Task 12: Hash-pin the ICO in tests.**
  - File: `tests/test_ico_placeholder.py` (new)
  - Action:
    - Compute SHA-256 of `packaging/USDCheckerUI.ico` once during
      Task 3 (script prints it). Paste the literal into a constant
      `_EXPECTED_SHA256 = "<64 hex chars>"`.
    - `test_committed_ico_matches_hash`: read the file bytes, assert
      `hashlib.sha256(data).hexdigest() == _EXPECTED_SHA256`.
    - `test_generator_produces_identical_bytes`: import `_generate_ico`
      module, call its generator function with `tmp_path` as output
      directory, assert the emitted bytes match
      `packaging/USDCheckerUI.ico` byte-for-byte.
  - Notes: `_generate_ico.py` must expose its write-logic as a callable
    (e.g., `generate(output_dir: Path) -> Path`) in addition to the
    `__main__` behavior, so Task 12 can call it without shelling out.

- [ ] **Task 13: Guard the `_keep_path` rewrite with a unit test.**
  - File: `tests/test_conftest_keep_path.py` (new)
  - Action: Import `_keep_path` from `tests.conftest` (or replicate the
    function signature via `importlib`). Parametrize with inputs that
    simulate typical Windows stdlib shapes (e.g.
    `"C:\\Python312\\Lib"`, `"C:\\Python312\\Lib\\site-packages"`) and
    mac shapes. Monkeypatch `sysconfig.get_paths` to return matching
    anchors. Assert `_keep_path` returns True for stdlib and
    site-packages under the mocked anchors, False for unrelated paths
    (e.g. `"/opt/foreign/usd/build/lib"`).
  - Notes: This is the regression gate for F13.

- [ ] **Task 14: Local verification with clean build dirs.**
  - Files: n/a (dev command sequence).
  - Action (blocking for handoff, NOT "deferred"):
    - On macOS: `rm -rf build dist && ruff check . && lint-imports && pytest`.
      Then `rm -rf build dist && pyinstaller packaging/pyinstaller.macos.spec --noconfirm`;
      smoke-test that `dist/USDCheckerUI.app` launches.
    - On Windows 10+ x64 (with VC++ Redist installed): `Remove-Item
      -Recurse -Force build, dist` → `pytest` (all green) →
      `Remove-Item -Recurse -Force build, dist` →
      `pyinstaller packaging\pyinstaller.windows.spec --noconfirm`;
      launch `dist\USDCheckerUI\USDCheckerUI.exe` and run the manual
      smoke checklist from the README Windows section. Verify
      `%LOCALAPPDATA%\USDCheckerUI\crash.log` is absent on a clean
      launch; verify it is populated if PYTHONPATH is intentionally
      polluted to induce a crash (sanity check for Task 5).
  - Notes: No Windows binary may be handed off until AC 1, AC 3, AC 9
    are green on a real Win10+ x64 host. If the implementation PR lands
    ahead of that verification, flag internal-only in the commit body
    and gate the handoff on a follow-up verification note.

### Acceptance Criteria

- [ ] **AC 1 (manual smoke, blocking for handoff) — Windows build
  produces a runnable exe.** Given a Windows 10+ x64 host with Python
  3.12, the VC++ 2015–2022 Redistributable x64 installed, and
  `pip install -e ".[dev]"` completed, when the developer cleans
  `build\` and `dist\` and runs
  `pyinstaller packaging\pyinstaller.windows.spec --noconfirm` from the
  repo root, then `dist\USDCheckerUI\USDCheckerUI.exe` exists and
  launches without `crash.log` being created (clean startup). This AC
  is manual; a dev eyeballs it per the README Windows smoke checklist.

- [ ] **AC 2 — macOS build is preserved after the rename.** Given the
  baseline dev setup on Mac ARM, when the developer cleans `build/` and
  `dist/` and runs
  `pyinstaller packaging/pyinstaller.macos.spec --noconfirm`, then
  `dist/USDCheckerUI.app` is produced and launches identically to the
  pre-change behavior.

- [ ] **AC 3 (manual smoke) — Windows exe shows the placeholder icon.**
  Given the exe built in AC 1, when the user launches
  `USDCheckerUI.exe`, then the window title bar and Windows taskbar
  entry display an icon (not the generic PyInstaller/Python default).
  Verified visually; blocking for handoff.

- [ ] **AC 4 (automated) — ICO is hash-pinned and reproducible.** Given
  `packaging/USDCheckerUI.ico` and `packaging/_generate_ico.py`, when
  `pytest tests/test_ico_placeholder.py` runs, then both the committed
  file's SHA-256 matches `_EXPECTED_SHA256` and a fresh call to the
  generator produces byte-identical output.

- [ ] **AC 5 — Popen failure raises the typed launch error.** Given
  `shutil.which("code")` returns a truthy string and `subprocess.Popen`
  raises `OSError("nope")`, when
  `editor_launcher.open_in_vscode(file, 1)` is called, then
  `EditorLaunchFailedError` is raised and its `str(...)` contains
  `"nope"`.

- [ ] **AC 6 — Missing CLI path is unchanged.** Given
  `shutil.which("code")` returns `None`, when
  `editor_launcher.open_in_vscode(file, 1)` is called, then
  `EditorNotAvailableError` is raised (no semantic change vs pre-spec).

- [ ] **AC 7 — UI shows a toast on launch failure.** Given the main
  window with a `.usda` loaded and `editor_launcher.open_in_vscode`
  patched to raise `EditorLaunchFailedError("boom")`, when the user
  triggers "Open in VSCode", then the status bar shows a toast whose
  text contains `"VSCode launch failed"` and `"boom"`, and no
  `QMessageBox` is opened.

- [ ] **AC 8 — `_vscode_missing_text` covers three platform branches.**
  Given `_vscode_missing_text("darwin")`, then the result contains
  `"Cmd+Shift+P"` and `"Shell Command"` (byte-identical to the
  pre-spec AC 19 pin). Given `_vscode_missing_text("win32")`, then the
  result contains `"Ctrl+Shift+P"` and `"Add to PATH"` and does NOT
  contain `"Cmd+Shift+P"`. Given `_vscode_missing_text("linux")`, then
  the result contains `"VSCode"` and `"PATH"` and contains neither
  `"Cmd+Shift+P"` nor `"Ctrl+Shift+P"`. All three assertions run on
  any host.

- [ ] **AC 9 (automated) — Pytest suite passes on Windows.** Given a
  Windows 10+ x64 host with dev install, when the developer clears
  `PYTHONPATH` and runs `pytest`, then the full suite — including the
  new `test_ico_placeholder`, `test_conftest_keep_path`, the Popen
  argv pin, and the three-branch `_vscode_missing_text` tests — passes
  with zero failures.

- [ ] **AC 10 — Pytest suite passes on macOS (regression).** Given a
  Mac ARM host with dev install, when the developer runs `pytest`,
  then the full suite passes with zero failures.

- [ ] **AC 11 — README has parallel Windows subsections + required
  notes.** Given `README.md`, when searched, then each of
  "Requirements", "Dev install", "Run the app (dev)", "Tests", and
  "Build" has a `### Windows` subsection; "MVP target: Mac ARM" no
  longer appears; the Windows Requirements section lists the VC++
  Redist; a SmartScreen/MOTW paragraph is present; the unambiguous
  PYTHONPATH idiom (cmd + PS forms) is present; the Icon one-liner is
  present under Windows — Build; the macOS build command references
  `pyinstaller.macos.spec`; both Build subsections mention the
  `build/` + `dist/` clean step.

- [ ] **AC 12 — Architecture contract is unchanged.** Given the code
  changes in this spec, when `lint-imports` is run, then the
  `core-no-qt` contract reports zero violations.

- [ ] **AC 13 (automated) — Popen receives the resolved VSCode path.**
  Given `shutil.which("code")` returns `"/resolved/code.cmd"`, when
  `editor_launcher.open_in_vscode(file, 1)` is called with a captured
  `Popen`, then the captured argv is
  `["/resolved/code.cmd", "--goto", f"{file}:1:1"]` — verifying F12's
  fix.

- [ ] **AC 14 (automated) — `conftest._keep_path` preserves Windows
  stdlib paths.** Given `sysconfig.get_paths()` is stubbed to return
  `{"stdlib": "C:\\Python312\\Lib", "platstdlib": "C:\\Python312\\Lib",
  "purelib": "C:\\Python312\\Lib\\site-packages", "platlib":
  "C:\\Python312\\Lib\\site-packages"}`, when `_keep_path` is called
  with each of `"C:\\Python312\\Lib"`,
  `"C:\\Python312\\Lib\\site-packages\\foo"`, and an unrelated
  `"/opt/foreign/usd/build/lib"`, then the first two return `True`
  and the third returns `False`.

- [ ] **AC 15 — `sys.excepthook` writes a crash log.** Given the app
  entry `__main__` has been imported (side effect: hook installed),
  when a synthetic exception is raised and `sys.excepthook(type(exc),
  exc, exc.__traceback__)` is called, then the configured per-user
  log file exists, is non-empty, contains the exception type name and
  message, and the previous hook was invoked (observable via a
  monkeypatched sentinel). Test uses `tmp_path` + an env-var override
  for the log dir so it doesn't touch the real user profile.

## Additional Context

### Dependencies

- **PyInstaller ≥ 6.10** — already in `dev` extra. No new package.
- **Python 3.12** on the Windows host (via `py -3.12`, `python.org`
  installer, or `pyenv-win`). Matches
  `pyproject.toml`'s `requires-python = ">=3.12,<3.13"`.
- **Microsoft Visual C++ 2015–2022 Redistributable (x64)** on every
  Windows target host. `usd-core`'s `.pyd` files link against the
  MSVC CRT (`vcruntime140.dll`, `msvcp140.dll`, `vcomp140.dll`);
  `collect_all("pxr")` does NOT copy these in when they live in
  System32. Missing redist causes an immediate import failure with
  no visible error under `console=False` — the crash log catches it
  (Task 5) but prevention is documented in the README.
- **VSCode with `code` on PATH** — optional, only for the "Open in
  VSCode" best-effort path. If absent, the app shows the
  platform-aware missing-CLI message.
- `pxr` wheels on Windows ship native `.pyd` + DLLs, handled uniformly
  by `collect_all("pxr")`.

### Testing Strategy

- **Automated unit tests (run on every host):**
  - Existing suite passes on Windows thanks to Task 10's `_keep_path`
    rewrite.
  - Task 8: `EditorLaunchFailedError` raised on `Popen` failure (AC 5);
    `Popen` argv pinned to resolved path (AC 13).
  - Task 9: three-branch coverage for `_vscode_missing_text` (AC 8).
  - Task 12: hash-pinned ICO + generator byte-identity (AC 4).
  - Task 13: `_keep_path` regression tests with mocked sysconfig (AC 14).
  - `sys.excepthook` write-to-log test (AC 15).
- **Static checks:**
  - `ruff check .` passes.
  - `lint-imports` passes (AC 12).
- **Manual Windows smoke (Win10+ x64 host, VC++ Redist installed) —
  blocking for handoff:**
  1. Fresh clone, `py -3.12 -m venv .venv`, activate,
     `pip install -e ".[dev]"`.
  2. `Remove-Item -Recurse -Force build, dist` (if present).
  3. `pyinstaller packaging\pyinstaller.windows.spec --noconfirm`.
  4. Launch `dist\USDCheckerUI\USDCheckerUI.exe` — main window visible;
     window icon is the placeholder (AC 3); no file at
     `%LOCALAPPDATA%\USDCheckerUI\crash.log`.
  5. Drag `tests\fixtures\minimal_invalid.usda` → diagnostic
     `ShaderPropertyTypeConformanceChecker` visible.
  6. Export → JSON → open in editor → structure valid.
  7. Click "Open in VSCode" on the `.usda` → VSCode launches (validates
     the resolved-path fix for `code.cmd`) OR a toast with the
     Windows-flavored text appears (if `code` is not on PATH).
  8. Intentional crash check: set `$env:PYTHONPATH =
     "C:\fake\bad\pxr"` in a fresh shell and relaunch — expect
     `crash.log` to be populated with a traceback.
  9. Close app.
- **Manual macOS regression smoke:** `rm -rf build dist`, rebuild from
  `pyinstaller.macos.spec`, repeat the existing Manual smoke checklist
  from the README.

### Notes

- **Bundle size risk (high).** `collect_all("pxr")` on Windows may pull
  the rendering submodules (`UsdImagingGL`, `Hgi*`) that the validator
  does not use, inflating the folder well past the macOS ~205 MB
  baseline. Measure post-build; if above ~400 MB, add
  `excludes=["pxr.UsdImagingGL", "pxr.Hgi", "pxr.HgiGL", "pxr.Hd",
  "pxr.HdSt", "pxr.UsdImaging"]` to `Analysis(...)` — matches the
  suggestion already in the README for macOS.
- **MSVC Redistributable posture (F9).** We document the prerequisite
  rather than bundling the redist DLLs ourselves. Rationale: bundling
  has licensing caveats and private-side-by-side assembly handling is
  non-trivial; documentation is sufficient for the internal-handoff
  delivery model. A future iteration with a real installer (NSIS/MSI)
  would bundle `vc_redist.x64.exe` as a per-machine install step.
- **SmartScreen / download blocks (known limitation).** Without
  authenticode signing, first-run SmartScreen flags the exe on clean
  Win10+ machines. Zipped downloads may carry Mark-of-the-Web and need
  "Unblock". Both are user-facing in the README; no code change.
- **`code.cmd` edge case.** Task 6 now passes the full resolved path
  from `shutil.which("code")` to `Popen`, so `.cmd` shims launch
  correctly on Windows. If `PATHEXT` is neutered and `.CMD` is not in
  it, detection still fails gracefully via `EditorNotAvailableError`.
- **ICO reproducibility is hash-pinned, not `git status`-gated (F2).**
  A developer editing `_generate_ico.py` can still produce a valid
  ICO, but AC 4's hash will fail until the `_EXPECTED_SHA256` literal
  in `tests/test_ico_placeholder.py` is updated in the same commit —
  forcing a conscious acknowledgement.
- **AC-as-manual-smoke (F10).** AC 1 and AC 3 are explicitly labelled
  manual smoke, not automated ACs. They gate the handoff, not the PR
  merge. The distinction is deliberate: "can we handoff?" vs. "is the
  code right?"
- **Ack — test argv pinning (F4).** Task 8 already pins `Popen` argv
  against the resolved path; the F4 concern is covered without a
  separate AC.
- **Ack — conftest assumption (F17).** "cross-platform" is now
  substantiated by Task 10 (sysconfig-based `_keep_path`) and Task 13
  (explicit unit test with mocked Windows shapes).
- **Ack — Unicode arrow codepoint (F22).** All three branches of
  `_vscode_missing_text` encode arrows as `"→"` escapes in source;
  the pinned expected strings in Task 9 do the same, so a
  copy-paste-from-editor mistake cannot silently swap the glyph.
- **Future iterations (out of scope here, worth noting):**
  `VSVersionInfo` / PE metadata block (F14), GitHub Actions with
  `windows-latest` + `macos-latest` matrix, authenticode signing step,
  NSIS or MSI installer (which would bundle the VC++ Redist install
  step), a real designed icon asset, a real dark-mode pass on
  Windows 11.
- **Commit-message style** in this repo is imperative mood + body
  explaining the why (see the initial commit). Mirror that during
  implementation. All source / doc / commit content stays in English
  per repo convention; French is reserved for interactive chat.
