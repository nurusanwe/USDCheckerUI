"""User-configured shader plugin paths.

Registers additional plugin metadata into the pxr Plug registry so that
`Sdr` discovery sees renderer-specific shader types (Houdini Karma,
Renderman Pxr*, in-house studio shaders, and any shader library that
ships its own Sdr plugin) instead of flagging them as "Shader
identifier not found in Sdr registry".

Qt-free by design: this module only touches pxr.Plug and a YAML config
on disk. The UI layer imports it to read/write the path list and to
trigger re-registration on change.

Lifecycle note
--------------
pxr.Plug has no unregistration API. Removing a path from the config
takes effect on the NEXT app launch, not immediately — the in-process
Plug registry keeps the plugin it already discovered. This is a pxr
limitation; the UI surfaces it as a toast.

Config file
-----------
Plain YAML list of path strings, persisted to:
  macOS  : ~/Library/Application Support/USDCheckerUI/shader_plugins.yaml
  Windows: %APPDATA%\\USDCheckerUI\\shader_plugins.yaml
  Other  : ~/.config/USDCheckerUI/shader_plugins.yaml
"""

from __future__ import annotations

import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class RegistrationResult:
    """Outcome of one pxr.Plug.RegisterPlugins call.

    Surfaced to the UI so a failing path (broken plugInfo.json, missing
    directory) can be reported without blocking the others.
    """
    path: Path
    ok: bool
    error: str | None = None


def _default_config_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "USDCheckerUI"
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", str(Path.home())))
        return base / "USDCheckerUI"
    return Path.home() / ".config" / "USDCheckerUI"


_CONFIG_DIR = _default_config_dir()
_CONFIG_FILE = _CONFIG_DIR / "shader_plugins.yaml"


def config_file_path() -> Path:
    """Absolute path to the on-disk YAML. Exposed for tests + UI 'open in
    system editor' affordances."""
    return _CONFIG_FILE


def load_configured_paths() -> list[Path]:
    """Return the user's configured paths in author-order.

    Missing file, empty file, or a malformed YAML → empty list. A warning
    is emitted via the `warnings` module for the malformed case so the
    log/crash-hook pipeline sees it but the app keeps running.
    """
    if not _CONFIG_FILE.exists():
        return []
    try:
        data = yaml.safe_load(_CONFIG_FILE.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        warnings.warn(
            f"shader_plugins.yaml is malformed, ignoring: {exc}",
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


def save_configured_paths(paths: list[Path]) -> None:
    """Persist `paths` to the YAML config, de-duplicated (first-wins)
    by exact string representation. Caller is responsible for giving
    absolute paths — the UI file picker already does."""
    seen: set[str] = set()
    unique: list[Path] = []
    for p in paths:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(
        yaml.safe_dump([str(p) for p in unique], sort_keys=False),
        encoding="utf-8",
    )


def add_path(path: Path) -> list[Path]:
    """Append `path` to the config if not already present.

    Returns the new path list (post-save). Use `register_paths([path])`
    separately to push the addition into the live Plug registry.
    """
    paths = load_configured_paths()
    absolute = path.expanduser()
    if not absolute.is_absolute() and absolute.exists():
        absolute = absolute.resolve()
    existing_strs = {str(p) for p in paths}
    if str(absolute) not in existing_strs:
        paths.append(absolute)
        save_configured_paths(paths)
    return paths


def remove_path(path: Path) -> list[Path]:
    """Drop `path` from the config and persist.

    Returns the new path list (post-save). Note that pxr.Plug cannot
    un-register a plugin in the current process — the UI must surface
    "next app launch" as the effective horizon.
    """
    paths = load_configured_paths()
    target = str(path.expanduser())
    kept = [p for p in paths if str(p) != target]
    save_configured_paths(kept)
    return kept


def register_paths(paths: list[Path]) -> list[RegistrationResult]:
    """Register each path with pxr's Plug registry.

    Accepted input shapes for each `path`:
      - A directory that contains `plugInfo.json` directly.
      - A `plugInfo.json` file path itself.
    `pxr.Plug.RegisterPlugins` does NOT recurse into subdirectories; a
    plugin tree that ships a top-level `plugInfo.json` with an
    `Includes` field is handled by pxr natively, nothing special
    required here.

    Each path is tried independently: if one fails (missing file,
    malformed plugInfo), the others still register. Results are
    returned in input order so the caller can pair them back with
    UI list entries.
    """
    # pxr is imported lazily so unit tests can stub `register_paths`
    # without pulling in the full pxr ABI.
    from pxr import Plug

    registry = Plug.Registry()
    results: list[RegistrationResult] = []
    for p in paths:
        try:
            if not p.exists():
                raise FileNotFoundError(f"path does not exist: {p}")
            registry.RegisterPlugins(str(p))
            results.append(RegistrationResult(path=p, ok=True))
        except Exception as exc:  # noqa: BLE001 — pxr raises many types
            results.append(
                RegistrationResult(
                    path=p,
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    return results


def register_configured() -> list[RegistrationResult]:
    """Load the on-disk path list and register each. Convenience wrapper
    for warmup and for the UI's "re-register all" button if we add one."""
    return register_paths(load_configured_paths())
