"""Known built-in shader identifiers.

USDChecker UI ships a handful of .usda files under `bundled_shaders/`
that declare shader identifiers which are legitimate in their
consuming pipeline but which pxr's Sdr registry cannot validate in a
bare usd-core environment. When the runner sees a
`ShaderPropertyTypeConformanceChecker / "has invalid shader node"`
diagnostic whose Shader prim carries a matching `info:id`, it
suppresses the diagnostic.

Two sources feed the suppression set
------------------------------------

1. Bundled (ships with the app):
   `src/usdchecker_ui/core/bundled_shaders/*.usda`. Every .usda in
   this directory is parsed; every `def Shader` prim's `info:id`
   contributes. Currently: Adobe Standard Material + a small curated
   MaterialX surface shader set. Grow by dropping more .usda files
   in that directory and rebuilding.

2. User-configured (added via Settings -> Additional shader
   definitions...): a YAML list of .usda paths alongside the app
   config, parsed at every `known_shader_ids()` refresh (the cache
   is busted after add/remove).

Why this can't go through `pxr.Plug` properly
---------------------------------------------
The shaders declare `info:implementationSource = "id"` with NO
source asset / source code attached. pxr's bundled parsers (glslfx,
USD) need a source type the parser can consume to build an
`SdrShaderNode`. Without source, the discovery path emits zero
results. The dynamic Python side of Sdr's plugin API is also
effectively closed — `Sdr.DiscoveryPlugin` cannot be subclassed
from Python, `SetExtraDiscoveryPlugins` / `SetExtraParserPlugins`
only accept TfType references to C++ classes, and
`AddDiscoveryResult` silently drops results whose `sourceType`
no parser can consume.

So we parse the .usda files directly, collect the `info:id` of
every Shader prim inside, and the runner consults this set to
suppress the specific "has invalid shader node" diagnostic.

Qt-free by design: only pxr.Usd + pxr.UsdShade + PyYAML are touched.
"""

from __future__ import annotations

import functools
import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

import yaml

# --- bundled files -------------------------------------------------------

_BUNDLED_DIR = Path(__file__).with_name("bundled_shaders")


def bundled_shader_defs_dir() -> Path:
    """Absolute path to the directory that holds the bundled .usda files.
    Exposed for tests and for the PyInstaller spec."""
    return _BUNDLED_DIR


def _bundled_usda_paths() -> list[Path]:
    if not _BUNDLED_DIR.exists():
        return []
    return sorted(_BUNDLED_DIR.glob("*.usda"))


# --- user-configured .usda sources --------------------------------------

def _default_config_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "USDCheckerUI"
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", str(Path.home())))
        return base / "USDCheckerUI"
    return Path.home() / ".config" / "USDCheckerUI"


_USER_CONFIG_DIR = _default_config_dir()
_USER_CONFIG_FILE = _USER_CONFIG_DIR / "known_shader_sources.yaml"


def user_config_file_path() -> Path:
    """Absolute path to the on-disk YAML that lists user-added .usda
    sources. Exposed for tests + the Settings dialog."""
    return _USER_CONFIG_FILE


def load_user_sources() -> list[Path]:
    """Return the user-configured list of .usda source paths in
    author-order. Missing / malformed file → empty list (with warning)."""
    if not _USER_CONFIG_FILE.exists():
        return []
    try:
        data = yaml.safe_load(_USER_CONFIG_FILE.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        warnings.warn(
            f"known_shader_sources.yaml is malformed, ignoring: {exc}",
            stacklevel=2,
        )
        return []
    if not isinstance(data, list):
        return []
    out: list[Path] = []
    for entry in data:
        if isinstance(entry, str) and entry.strip():
            out.append(Path(entry).expanduser())
    return out


def save_user_sources(paths: list[Path]) -> None:
    """Persist the user source list. Dedupes by string representation
    and resets the identifier cache so the next `known_shader_ids()`
    call picks up the change."""
    seen: set[str] = set()
    unique: list[Path] = []
    for p in paths:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    _USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _USER_CONFIG_FILE.write_text(
        yaml.safe_dump([str(p) for p in unique], sort_keys=False),
        encoding="utf-8",
    )
    # Invalidate the id cache so a subsequent validation sees the change.
    known_shader_ids.cache_clear()


def add_user_source(path: Path) -> list[Path]:
    """Append `path` to the user sources if not already present."""
    paths = load_user_sources()
    target = str(path.expanduser())
    existing = {str(p) for p in paths}
    if target not in existing:
        paths.append(path.expanduser())
        save_user_sources(paths)
    return paths


def remove_user_source(path: Path) -> list[Path]:
    """Drop `path` from the user sources."""
    paths = load_user_sources()
    target = str(path.expanduser())
    kept = [p for p in paths if str(p) != target]
    save_user_sources(kept)
    return kept


# --- identifier extraction ----------------------------------------------

@dataclass(frozen=True)
class SourceReport:
    """How one .usda contributed to the suppression set. Surfaced to
    the UI dialog so the user sees what each file added (and
    whether it failed)."""
    path: Path
    ids: frozenset[str]
    ok: bool
    error: str | None = None


def _extract_ids_from_usda(path: Path) -> SourceReport:
    """Parse a single .usda, return the set of Shader `info:id` values
    declared inside. Errors never raise — they're packaged into
    `SourceReport.error` so the caller (UI or warmup) can surface
    them without blocking other sources."""
    if not path.exists():
        return SourceReport(path=path, ids=frozenset(), ok=False,
                            error=f"file does not exist: {path}")
    from pxr import Usd, UsdShade
    try:
        stage = Usd.Stage.Open(str(path))
    except Exception as exc:  # noqa: BLE001 — pxr raises many types
        return SourceReport(path=path, ids=frozenset(), ok=False,
                            error=f"{type(exc).__name__}: {exc}")
    if stage is None:
        return SourceReport(path=path, ids=frozenset(), ok=False,
                            error="Usd.Stage.Open returned None")
    ids: set[str] = set()
    for prim in stage.Traverse():
        if not prim.IsA(UsdShade.Shader):
            continue
        shader = UsdShade.Shader(prim)
        ident = shader.GetShaderId()
        if ident:
            ids.add(ident)
    return SourceReport(path=path, ids=frozenset(ids), ok=True)


def report_all_sources() -> list[SourceReport]:
    """Return a per-file breakdown: bundled first (in filename order),
    then user-configured (in author order). Used by the Settings
    dialog to show what each file contributed."""
    reports: list[SourceReport] = []
    for p in _bundled_usda_paths():
        reports.append(_extract_ids_from_usda(p))
    for p in load_user_sources():
        reports.append(_extract_ids_from_usda(p))
    return reports


@functools.lru_cache(maxsize=1)
def known_shader_ids() -> frozenset[str]:
    """Union of every `info:id` declared by every bundled and
    user-configured .usda source. Cached; `save_user_sources` busts
    the cache."""
    all_ids: set[str] = set()
    for report in report_all_sources():
        if report.ok:
            all_ids |= report.ids
        # report.error is surfaced via report_all_sources() for the UI;
        # warmup also logs it via warnings.
    return frozenset(all_ids)


# --- backward-compat shim -----------------------------------------------

def bundled_shader_defs_path() -> Path:
    """Deprecated: the first bundled .usda file, kept for backward
    compatibility with code that referenced the single-file era."""
    paths = _bundled_usda_paths()
    return paths[0] if paths else _BUNDLED_DIR / "shader_definitions.usda"
