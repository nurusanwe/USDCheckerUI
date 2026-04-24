"""Known built-in shader identifiers.

USDChecker UI ships a snapshot of a third-party shader-definitions file
(`bundled_shaders/shader_definitions.usda`) that declares shader
identifiers which are legitimate in the consuming pipeline (e.g.
`AdobeStandardMaterial_4_0`) but which pxr's Sdr registry in a bare
usd-core environment cannot validate.

Why this can't go through `pxr.Plug` properly
---------------------------------------------
The shaders declare `info:implementationSource = "id"` with NO
source asset / source code attached. pxr's bundled parsers (glslfx,
USD) need a source type the parser can consume to build an
`SdrShaderNode`. Without source, the discovery path emits zero
results (`UsdShade.ShaderDefUtils.GetDiscoveryResults` returns
empty for these prims). The dynamic Python side of Sdr's
plugin API is also effectively closed — `Sdr.DiscoveryPlugin`
cannot be subclassed from Python ("This class cannot be
instantiated from Python"), `SetExtraDiscoveryPlugins` /
`SetExtraParserPlugins` only accept TfType references to C++
classes, and `AddDiscoveryResult` silently drops results whose
`sourceType` no parser can consume.

So: we parse the bundled .usda once, collect the `info:id` of every
Shader prim inside, and the runner consults this set to suppress the
specific "has invalid shader node" diagnostic that would otherwise
fire for legitimate uses of these identifiers.

Qt-free by design: only pxr.Usd + pxr.UsdShade are touched.
"""

from __future__ import annotations

import functools
from pathlib import Path

_BUNDLED_SHADER_DEFS = (
    Path(__file__).with_name("bundled_shaders") / "shader_definitions.usda"
)


def bundled_shader_defs_path() -> Path:
    """Absolute path to the shipped shader_definitions.usda. Exposed for
    tests + for the PyInstaller spec to reference the file explicitly."""
    return _BUNDLED_SHADER_DEFS


@functools.lru_cache(maxsize=1)
def known_shader_ids() -> frozenset[str]:
    """Return the `info:id` values declared by every Shader prim in the
    bundled shader_definitions.usda.

    First-call parses the file (~40 KB, ~900 lines) and caches the
    result for the rest of the process. Returns an empty frozenset if
    the bundled file is missing — e.g. a development install that
    excluded `bundled_shaders/` — so the runner falls back to the
    unsuppressed path transparently.
    """
    if not _BUNDLED_SHADER_DEFS.exists():
        return frozenset()
    from pxr import Usd, UsdShade
    try:
        stage = Usd.Stage.Open(str(_BUNDLED_SHADER_DEFS))
    except Exception:
        return frozenset()
    if stage is None:
        return frozenset()
    ids: set[str] = set()
    for prim in stage.Traverse():
        if not prim.IsA(UsdShade.Shader):
            continue
        shader = UsdShade.Shader(prim)
        ident = shader.GetShaderId()
        if ident:
            ids.add(ident)
    return frozenset(ids)
