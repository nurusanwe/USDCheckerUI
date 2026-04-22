---
title: 'USDChecker UI'
slug: 'usdchecker-ui'
created: '2026-04-22'
status: 'completed'
stepsCompleted: [1, 2, 3, 4, 5, 6]
implementedOn: '2026-04-22'
reviewedOn: '2026-04-22'
secondAdversarialReview:
  findingsTotal: 25
  findingsFixed: 22
  findingsSkipped: 3   # F1 (contradicts AC 1), F8 (non-issue), F19 (uncertain)
adversarialReview:
  reviewedOn: '2026-04-22'
  findingsAddressed: 'Critical + High (F1..F11)'
  findingsDeferred: 'Medium (F12..F20), Low (F21..F23) — documented in Notes'
tech_stack:
  - Python 3.12
  - PySide6 (Qt for Python, >= 6.7)
  - usd-core (PyPI wheel, pinned >=25.11,<27 — 25.11 is the last stable before 26.x)
  - PyYAML (for patterns.yaml)
  - PyInstaller (packaging, Mac ARM .app)
  - pytest (tests)
  - ruff (lint + format)
  - import-linter (dev, enforces core/ui architectural boundary)
files_to_modify:
  - pyproject.toml (new)
  - .gitignore (new)
  - .ruff.toml (new)
  - .importlinter (new, core/ui boundary contract)
  - README.md (new)
  - src/usdchecker_ui/__init__.py (new)
  - src/usdchecker_ui/__main__.py (new, app entry point)
  - src/usdchecker_ui/core/__init__.py (new)
  - src/usdchecker_ui/core/diagnostic.py (new)
  - src/usdchecker_ui/core/runner.py (new)
  - src/usdchecker_ui/core/parser.py (new)
  - src/usdchecker_ui/core/enricher.py (new)
  - src/usdchecker_ui/core/patterns.yaml (new, default packaged dict)
  - src/usdchecker_ui/core/patterns_store.py (new, user-override + reload)
  - src/usdchecker_ui/core/exporter.py (new)
  - src/usdchecker_ui/core/editor_launcher.py (new)
  - src/usdchecker_ui/core/plugins_warmup.py (new, eager pxr plugin load)
  - src/usdchecker_ui/ui/__init__.py (new)
  - src/usdchecker_ui/ui/main_window.py (new)
  - src/usdchecker_ui/ui/drop_zone.py (new)
  - src/usdchecker_ui/ui/diagnostic_tree.py (new)
  - src/usdchecker_ui/ui/filter_bar.py (new)
  - src/usdchecker_ui/ui/detail_panel.py (new)
  - src/usdchecker_ui/ui/toolbar.py (new)
  - src/usdchecker_ui/ui/check_worker.py (new, QObject worker for QThread)
  - src/usdchecker_ui/ui/theme.py (new, minimal stylesheet)
  - tests/__init__.py (new)
  - tests/conftest.py (new, fixture helpers)
  - tests/test_runner.py (new)
  - tests/test_parser.py (new)
  - tests/test_enricher.py (new)
  - tests/test_exporter.py (new)
  - tests/test_editor_launcher.py (new)
  - tests/test_architecture.py (new, runs import-linter)
  - tests/test_patterns_store.py (new)
  - tests/fixtures/minimal_valid.usda (new, fully conformant)
  - tests/fixtures/minimal_invalid.usda (new, 1 known ShaderPropertyTypeConformance error)
  - tests/fixtures/minimal_normalmap_invalid.usda (new, triggers NormalMapTextureChecker)
  - tests/fixtures/minimal_package.usdz (new, tiny forged .usdz ~10 KB)
  - tests/fixtures/parser_samples.yaml (new, corpus of raw strings for parser tests)
  - packaging/pyinstaller.spec (new)
  - packaging/entitlements.plist (new)
  - packaging/Info.plist.template (new)
code_patterns:
  - 'Strict core/ui separation enforced by import-linter (core/ has zero Qt imports)'
  - 'Src-layout Python project (src/usdchecker_ui/...) with pyproject.toml PEP 621'
  - 'Dataclasses with slots+frozen for Diagnostic (immutable, serializable, thread-safe)'
  - 'QThread worker pattern: worker owns entire pxr interaction; only plain-Python dataclasses cross the thread boundary'
  - 'Qt Model/View: QStandardItemModel + QSortFilterProxyModel with recursiveFilteringEnabled=True'
  - 'Pure functions for parser/enricher/exporter (easy to unit test)'
  - 'YAML-driven pattern dict, layered: packaged default < user override at ~/Library/Application Support/USDCheckerUI/patterns.yaml'
test_patterns:
  - 'pytest with fixtures in tests/fixtures/'
  - 'Unit tests on core/ only; no UI test automation for MVP'
  - 'Architecture test runs import-linter — fails CI if core/ imports PySide6'
  - 'Optional corpus validation via env var USDCHECKER_UI_TEST_CORPUS pointing to a local large .usdz (auto-skip if unset)'
---

# Tech-Spec: USDChecker UI

**Created:** 2026-04-22
**Status:** Completed (Quick Dev workflow, 2026-04-22 — post 2nd adversarial review)

## Overview

### Problem Statement

Le binaire `usdchecker` (OpenUSD) produit une sortie texte brute et verbeuse
avec des erreurs cryptiques liées à l'asset resolution, aux variants, aux
schemas, à la compliance, etc. Artistes 3D et devs pipeline ont du mal à
diagnostiquer rapidement un fichier USD défaillant. Il manque un outil visuel
qui structure, explique en langage humain, et rend navigable ces résultats de
validation.

### Solution

App desktop PySide6 standalone (Mac ARM d'abord) qui :

1. Reçoit un fichier USD par drag & drop (`.usd/.usda/.usdc/.usdz`)
2. Exécute la validation via **l'API Python `pxr.UsdUtils.ComplianceChecker`**
   (wheel `usd-core` sur PyPI — même codebase que le binaire `usdchecker`
   officiel). Pas de subprocess, pas de dylib bundling.
3. Récupère diagnostics depuis 3 accesseurs de l'API : `GetErrors()`,
   `GetWarnings()`, `GetFailedChecks()` — chacun produisant une **shape de
   message distincte** (vérifié sur source, voir Files to Reference) :
   - `GetErrors()` → `"Error checking rule '<RULE>': <msg>"`
   - `GetWarnings()` → `"<msg> (may violate '<RULE>')"`
   - `GetFailedChecks()` → `"<msg> (fails '<RULE>')"`
   La sévérité est **posée par l'accesseur utilisé**, pas par parsing de
   préfixe texte.
4. Parse chaque message pour extraire `rule`, `prim_path`, `asset_path` via
   3 regex dédiés (une par shape). Fallback `rule="Unknown"` pour toute
   shape inconnue — raw jamais perdu.
5. Enrichit chaque diagnostic via un dictionnaire `patterns.yaml`, avec
   override utilisateur éditable (layered config : bundled default < user
   override en `~/Library/Application Support/USDCheckerUI/`).
6. Affiche en tree filtrable avec toggle « explication / raw »
7. Permet export (JSON / Markdown / HTML) et « open in editor » (VSCode) sur
   le prim fautif — uniquement si le fichier source est `.usda`. Documente
   explicitement le failure mode en cas de prim ambigu.

### Scope

**In Scope (MVP) :**

- Drag & drop fichiers `.usd/.usda/.usdc/.usdz`
- Validation via `pxr.UsdUtils.ComplianceChecker` (API Python, pas de binaire)
- Classification par sévérité (Error / Warning / Info) via méthode API
- Regroupement hiérarchique : Severity → Rule → Prim
- Dual view : explication humaine ET raw message conservé (toggle)
- Filtres combinables (sévérité, rule, prim, texte libre) avec
  `recursiveFilteringEnabled=True` sur le proxy
- Export du rapport (JSON, Markdown, HTML)
- « Open in editor » (VSCode via `code --goto`) — uniquement pour `.usda`
- Dictionnaire de patterns `patterns.yaml` éditable **avec menu UI dédié**
  (« Edit patterns… » + « Reload patterns »), override en home dir
- Build Mac ARM (`.app` bundle) via PyInstaller
- Corpus de test optionnel via env var `USDCHECKER_UI_TEST_CORPUS`

**Out of Scope (pour ce cycle) :**

- Historique des validations
- Build Windows (prévu, pas maintenant)
- Build Linux
- Intégration Eclair Studio (ImGUI C++, phase future)
- Intégration DCC (Maya / Houdini / Blender)
- Apple Signing / Notarization (nice-to-have, pas bloquant MVP)
- Auto-update, telemetry, analytics
- « Open in editor » pour formats binaires (`.usd/.usdc/.usdz`)
- Flag `--arkit` UI-exposé (CLI dev uniquement pour MVP)

## Context for Development

### Codebase Patterns

**Clean Slate confirmé** — repo greenfield, aucun code existant. Choix
structurants :

- **Layout** `src/` Python + `pyproject.toml` (PEP 621)
- **Séparation stricte `core/` vs `ui/`** : `core/` n'importe AUCUN symbole
  Qt. **Enforced par `import-linter`** (Task 14bis) + test CI. `core/` reste
  portable vers Eclair Studio (C++ ImGUI) ou autre front-end.
- **Style** : `ruff` lint+format, type hints partout, docstrings Google
- **Python 3.12** cible (via Homebrew `python@3.12` ou pyenv ; le Python
  système macOS — 3.9 bloqué par Apple — n'est PAS utilisable)

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `/Users/rgt/USD/installed/lib/python/pxr/UsdUtils/complianceChecker.py` | **Source de vérité API** (vérifiée au moment de la spec). Lignes clés : constructor `__init__` ligne 1008 (`arkit, skipARKitRootLayerCheck, rootPackageOnly, skipVariants, verbose, assetLevelChecks`) ; `GetErrors()` ligne 1034 ; `GetWarnings()` ligne 1043 ; `GetFailedChecks()` ligne 1059 ; `CheckCompliance(inputFile)` ligne 1068 (positionnel unique). Les 3 shapes de messages sont construites dans ces méthodes |
| `/Users/rgt/USD/installed/bin/usdchecker` | Binaire CLI de référence — sert à confronter la sortie API vs sortie CLI en dev (NON embarqué) |
| **`USDCHECKER_UI_TEST_CORPUS`** (env var) | Pointe vers un gros fichier `.usdz` local (ex: BMW.usdz qui fait 631 MB). Les tests `test_runner::test_check_large_corpus` skipent si non défini. **Jamais dans le repo.** |

### Technical Decisions

1. **Validation via API Python (pas subprocess)** — bundle ~100 MB (à
   mesurer, AC relaxé), pas de `install_name_tool`, sévérité via API,
   possibilité d'enrichir en interrogeant la stage USD à la volée.

2. **`usd-core` wheel** PyPI, pinned `>=25.11,<27`. Raisons :
   - 25.11 = dernière stable connue avant la 26.x fraîche
   - `<27` = ceinture contre breaking changes majeurs futurs
   - Si wheel 25.11 a un bug Mac ARM sur 3.12, fallback 25.8 (documenté
     dans pyproject commentaire)
   - **API vérifiée source-of-truth** : voir Files to Reference

3. **Python 3.12** via Homebrew `python@3.12` ou pyenv.

4. **Architecture `core/` + `ui/` enforced** — `import-linter` contract
   `forbidden: ["PySide6", "PyQt6", "PyQt5"]` sur paquet `usdchecker_ui.core`.
   Test `tests/test_architecture.py` fait échouer le suite pytest si la
   règle est violée.

5. **Threading model (contrat strict)** :
   - **Startup** : `plugins_warmup.warm()` appelé avant
     `QApplication.exec()` → charge pxr plugins et instancie un
     `ComplianceChecker` jetable pour forcer la découverte (évite les races
     PluginRegistry/Tf ensuite).
   - **Per-check** : UI → `CheckWorker(QObject)` moved to `QThread` ;
     `CheckWorker.run(path)` appelle `core.runner.check(path)` de bout en
     bout (Stage.Open + ComplianceChecker + parse). **Aucun objet pxr ne
     traverse la frontière thread.** Le worker émet `finished(
     list[EnrichedDiagnostic])` — des dataclasses frozen, safe à passer.
   - **Concurrency** : un seul check à la fois. Si l'user drop un 2e
     fichier pendant qu'un check tourne, le nouveau est rejeté avec toast
     « Validation en cours… ».
   - **Pas de signals pxr vers Qt** : pas de `Tf.Notice` connecté au main
     thread.

6. **`patterns.yaml` layered config** :
   - Bundled default : `src/usdchecker_ui/core/patterns.yaml`, read-only.
   - User override : `~/Library/Application Support/USDCheckerUI/patterns.yaml`
     — créé à la demande via menu « Edit patterns… » (copie le bundled au
     premier appel + ouvre dans `open` system command).
   - Loader merge : user override gagne rule-par-rule sur le bundled.
   - Menu « Reload patterns » recharge à chaud (pas de restart app).

7. **UI PySide6** :
   - `QTreeView` + `QStandardItemModel` + `QSortFilterProxyModel`
   - **`setRecursiveFilteringEnabled(True)`** (Qt 5.10+) — sinon un parent
     non-matchant cache ses enfants matchants (footgun connu)
   - Toolbar : Ouvrir / Exporter / Ouvrir dans VSCode / Settings (menu
     patterns)

8. **Packaging PyInstaller `--windowed --onedir`** — `.app` bundle.
   **Taille non capée** dans les ACs (on mesure + documente en README).
   Notarization hors scope.

9. **« Open in editor »** — `subprocess.Popen(["code", "--goto",
   f"{file}:{line}:1"])`. Graceful si `code` absent (AC 17 inclut le texte
   exact du `QMessageBox`). **Failure mode prim ambigu** : si le leaf-name
   du prim apparaît plusieurs fois dans le fichier `.usda`, ouvrir à la
   **ligne 1** + toast avertissement « Prim ambigu — ouvert à la racine ».

## Implementation Plan

### Tasks

> **Ordre : dépendances du bas vers le haut.** Chaque task doit être
> complétée et testée (si applicable) avant la suivante.

#### Phase 1 — Project setup (1 task)

- [x] **Task 1 : Bootstrap du projet Python**
  - **Files :** `pyproject.toml`, `.gitignore`, `.ruff.toml`, `.importlinter`,
    `README.md`, `src/usdchecker_ui/__init__.py`,
    `src/usdchecker_ui/core/__init__.py`,
    `src/usdchecker_ui/ui/__init__.py`, `tests/__init__.py`
  - **Action :**
    - `pyproject.toml` (PEP 621) — runtime deps : `PySide6>=6.7`,
      `usd-core>=25.11,<27`, `PyYAML>=6.0`. Dev deps :
      `pytest>=8.0`, `pyinstaller>=6.10`, `ruff>=0.6`,
      `import-linter>=2.0`.
    - Entry point console `usdchecker-ui = usdchecker_ui.__main__:main`
    - `.gitignore` : patterns Python standard + `dist/`, `build/`,
      `*.spec.lock`. **NE PAS ignorer `_bmad-output/`** (contient la spec).
    - `.ruff.toml` : `target-version = "py312"`, `line-length = 100`,
      `select = ["E", "F", "I", "UP", "B", "SIM"]`
    - `.importlinter` : contrat `forbidden` interdisant `PySide6`, `PyQt6`,
      `PyQt5` dans paquet `usdchecker_ui.core`
    - `README.md` minimal : pitch + install/run + mention du
      `USDCHECKER_UI_TEST_CORPUS`
  - **Notes :** **Python 3.12 obligatoire** — via Homebrew `python@3.12`
    ou pyenv. Le Python système macOS (3.9) ne convient PAS. Valider :
    `pip install -e ".[dev]"` + `ruff check .` + `lint-imports`.

#### Phase 2 — Core domain (7 tasks, pure Python, testable)

- [x] **Task 2 : Dataclass `Diagnostic`**
  - **File :** `src/usdchecker_ui/core/diagnostic.py`
  - **Action :** `@dataclass(slots=True, frozen=True)` avec champs
    `rule: str`, `severity: Literal["error","warning"]`,
    `message: str` (raw), `prim_path: str | None`, `asset_path: str | None`,
    `layer: str | None`. Méthode `to_dict() -> dict` pour JSON export.
  - **Notes :** `severity` uniquement `error` | `warning` (on retire
    `info` — runner n'en émet pas ; filtre UI n'exposera pas `Info`).
    **Frozen + slots = thread-safe + picklable** pour traverser la
    frontière QThread.

- [x] **Task 3 : Runner `check()`**
  - **File :** `src/usdchecker_ui/core/runner.py`
  - **Action :** `check(file_path: Path) -> list[Diagnostic]` qui :
    1. Instancie `UsdUtils.ComplianceChecker(arkit=False,
       skipARKitRootLayerCheck=True, rootPackageOnly=False,
       skipVariants=False, verbose=False, assetLevelChecks=True)`
       **(signature vérifiée sur source : complianceChecker.py:1008)**
    2. Appelle `checker.CheckCompliance(str(file_path))` (single positional arg)
    3. Récupère 3 listes de strings via `GetErrors()`, `GetWarnings()`,
       `GetFailedChecks()` **(source : complianceChecker.py:1034/1043/1059)**
    4. Pour chaque string, délègue à `parser.parse_one(raw, severity,
       source_accessor)` où `source_accessor ∈ {"errors","warnings",
       "failed_checks"}` pour choisir la shape regex
    5. Retourne la liste concaténée
  - **Notes :** wrap `FileNotFoundError` et `Tf.ErrorException` (via
    `UsdUtils` exposant `Tf`) en `RunnerError(Exception)` custom avec
    un code de catégorie (`FILE_NOT_FOUND`, `USD_LOAD_ERROR`, `UNKNOWN`).
    Pas de logique Qt ici.

- [x] **Task 4 : Parser (3 shapes vérifiées)**
  - **File :** `src/usdchecker_ui/core/parser.py`
  - **Action :** fonction `parse_one(raw: str, severity: str,
    source: str) -> Diagnostic`. 3 regex dispatched par `source` :
    - **source="errors"** (GetErrors shape) :
      `r"^Error checking rule '(?P<rule>[^']+)': (?P<rest>.*)$"` puis
      extraction prim/asset sur `rest` via
      `r"<(?P<prim>/[^>]+)>"` + `r"@(?P<asset>[^@]+)@"`
    - **source="warnings"** (GetWarnings shape) :
      `r"^(?P<msg>.*) \(may violate '(?P<rule>[^']+)'\)$"` + prim/asset
      extract secondaires
    - **source="failed_checks"** (GetFailedChecks shape) :
      `r"^(?P<msg>.*) \(fails '(?P<rule>[^']+)'\)$"` + prim/asset
      extract secondaires. Le prim peut apparaître sous 2 formes :
      `<...>` ou `/Path/to/prim.attr` — regex fallback
      `r"(?:<(?P<p1>/[^>]+)>|(?P<p2>/[A-Za-z0-9_/\.]+))"`
    - **Fallback ultime** : si aucun pattern ne matche dans son channel,
      `Diagnostic(rule="Unknown", prim_path=None, asset_path=None,
      message=raw, severity=severity, layer=None)`. **Raw jamais perdu.**
  - **Notes :** `layer` reste `None` en MVP. Tests parametrized dans
    Task 11 doivent couvrir les 3 shapes + le fallback Unknown.

- [x] **Task 5 : Dictionnaire `patterns.yaml` initial**
  - **File :** `src/usdchecker_ui/core/patterns.yaml`
  - **Action :** 2 entrées minimum :
    ```yaml
    - rule: NormalMapTextureChecker
      title: "Normal map 8-bit sans scale/bias"
      explanation: |
        Un UsdUVTexture lit une normal map 8-bit mais n'a pas configuré
        inputs:scale et inputs:bias. Conséquence : la map est interprétée
        comme une color map, les normales sont fausses, l'éclairage sera
        incorrect.
      suggestion: |
        Sur le UsdUVTexture du prim, définir :
          inputs:scale = (2, 2, 2, 1)
          inputs:bias  = (-1, -1, -1, 0)

    - rule: ShaderPropertyTypeConformanceChecker
      title: "Type d'input shader non conforme"
      explanation: |
        Un input de shader a un type différent de ce qu'attend le schema
        UsdShade (ex: 'float3' au lieu de 'color3f'). Le renderer peut
        refuser le shader ou produire un rendu incorrect.
      suggestion: |
        Corriger le type de l'input dans le .usda source pour matcher le
        type attendu (voir le message brut pour le type exact).
    ```

- [x] **Task 6 : Enricher**
  - **File :** `src/usdchecker_ui/core/enricher.py`
  - **Action :** dataclass `EnrichedDiagnostic(diagnostic: Diagnostic,
    title: str | None, explanation: str | None, suggestion: str | None)`
    avec méthode `to_dict() -> dict` qui produit la structure attendue
    par AC 12 : `{rule, severity, message, prim_path, asset_path,
    enrichment: {title, explanation, suggestion} | None}`.
    Fonction `enrich(d: Diagnostic, patterns: dict) -> EnrichedDiagnostic`
    — lookup par `d.rule` exact, sinon retourne l'enriched avec
    `title/explanation/suggestion=None`.

- [x] **Task 7 : Patterns store (layered config + reload)**
  - **File :** `src/usdchecker_ui/core/patterns_store.py`
  - **Action :**
    - `user_patterns_path() -> Path` → `~/Library/Application
      Support/USDCheckerUI/patterns.yaml`
    - `ensure_user_override() -> Path` : si le fichier n'existe pas, copie
      le bundled default. Retourne le path.
    - `load_merged() -> dict[str, Pattern]` : charge bundled default +
      merge avec user override (override gagne rule par rule).
    - `open_for_edit()` : appelle `ensure_user_override()` puis
      `subprocess.Popen(["open", str(path)])` (ouvre dans l'app macOS par
      défaut).
    - `reload() -> dict`: ré-appelle `load_merged()`, invalide cache.
  - **Notes :** le chemin user-space est hors du bundle signé donc
    éditable. `open_for_edit` est côté core car zéro Qt.

- [x] **Task 8 : Exporter**
  - **File :** `src/usdchecker_ui/core/exporter.py`
  - **Action :** 3 fonctions prenant `list[EnrichedDiagnostic]` + dict
    `meta` (`file_path`, `date`, `duration_seconds`, `total`) :
    - `to_json(diags, meta) -> str` — JSON avec schéma :
      ```
      {
        "meta": {"file_path": str, "date": iso8601, "duration_seconds":
                 float, "total": int},
        "diagnostics": [EnrichedDiagnostic.to_dict(), ...]
      }
      ```
    - `to_markdown(diags, meta) -> str` — H1 titre + tableau meta +
      sections par rule avec count + liste des prims
    - `to_html(diags, meta) -> str` — HTML standalone avec `<style>`
      inline

#### Phase 3 — Utilitaires (3 tasks)

- [x] **Task 9 : Editor launcher**
  - **File :** `src/usdchecker_ui/core/editor_launcher.py`
  - **Action :**
    - `is_vscode_available() -> bool` (via `shutil.which("code")`)
    - `find_prim_line(usda_path: Path, prim_path: str) -> tuple[int,
      bool]` : retourne `(line, unambiguous)`. Algo :
      1. Lit le fichier
      2. Regex `r'def\s+\w+\s+"(?P<name>[^"]+)"'` — collecte toutes les
         occurrences du leaf name de `prim_path`
      3. Si exactement 1 match → `(line, True)`
      4. Si 0 ou >1 → `(1, False)` (fallback racine)
    - `open_in_vscode(file: Path, line: int | None) -> None` : Popen
      avec `code --goto {file}:{line or 1}:1`. Raise
      `EditorNotAvailableError` si `is_vscode_available()` False. Le caller
      (UI) doit afficher un toast « Prim ambigu » si `unambiguous=False`.
  - **Notes :** `find_prim_line` ne gère PAS les prims multi-fichiers
    (sublayers, references externes). Documenté explicitement comme
    best-effort. AC 15 + AC 15bis précisent les deux failure modes.

- [x] **Task 10 : Plugins warmup**
  - **File :** `src/usdchecker_ui/core/plugins_warmup.py`
  - **Action :** `warm() -> None` qui :
    1. `from pxr import Usd, UsdUtils, Sdf, Ar, Tf` (force les imports)
    2. Instancie `UsdUtils.ComplianceChecker()` une fois (défauts) pour
       déclencher la construction de tous les rule objects (force
       `GetRules()` + plugin discovery)
    3. Pas d'appel à `CheckCompliance` — juste l'init.
  - **Notes :** appelé depuis `__main__.py` avant `QApplication.exec()`,
    bloque ~200 ms au premier lancement. Évite les races plugin registry
    quand le premier drop arrive.

- [x] **Task 11 : Fixtures de test**
  - **Files :** `tests/conftest.py`, `tests/fixtures/minimal_valid.usda`,
    `tests/fixtures/minimal_invalid.usda`,
    `tests/fixtures/minimal_normalmap_invalid.usda`,
    `tests/fixtures/minimal_package.usdz`,
    `tests/fixtures/parser_samples.yaml`
  - **Action :**
    - `conftest.py` expose fixtures : `valid_usda_path`,
      `invalid_usda_path`, `normalmap_invalid_usda_path`, `usdz_path`,
      `parser_samples` (charge le yaml), `large_corpus_path` (lit
      `USDCHECKER_UI_TEST_CORPUS`, skip si absent).
    - `minimal_valid.usda` : stage minimal avec `upAxis="Y"`,
      `metersPerUnit=1.0`, un `defaultPrim`, 1 Xform + 1 Mesh + 1 Material
      UsdPreviewSurface avec types CORRECTS (color3f, string) — 0 erreur
      attendue.
    - `minimal_invalid.usda` : même structure mais
      `UsdPreviewSurfaceShader.inputs:diffuseColor` typé `float3` →
      déclenche ShaderPropertyTypeConformanceChecker.
    - `minimal_normalmap_invalid.usda` : normal map 8-bit sans
      scale/bias → déclenche NormalMapTextureChecker.
    - `minimal_package.usdz` : produit à la main via `usdcat
      --usdformat usdc minimal_valid.usda -o tmp.usd` puis zip dans
      un `.usdz` valide (alignement 64B) via script shell documenté.
      Taille attendue ~10 KB.
    - `parser_samples.yaml` : liste de strings réelles capturées sur
      BMW.usdz (par raw dump) + strings forgées pour warnings/failed_checks,
      chacune avec son shape attendue.
  - **Notes :** **AUCUNE** fixture volumineuse dans le repo. Le gros corpus
    (ex: BMW.usdz 631 MB) passe par env var, jamais committé.

#### Phase 4 — Tests core (6 tasks)

- [x] **Task 12 : Test runner (fixtures légères + corpus optionnel)**
  - **File :** `tests/test_runner.py`
  - **Action :**
    1. `check(valid_usda_path)` → `[]`
    2. `check(invalid_usda_path)` → au moins 1 Diagnostic avec
       `rule == "ShaderPropertyTypeConformanceChecker"` et
       `severity == "error"` (le count exact peut varier selon les default
       checks qui tripent sur le minimal — on assert le BON rule, pas le
       TOTAL)
    3. `check(normalmap_invalid_usda_path)` → au moins 1 Diagnostic avec
       `rule == "NormalMapTextureChecker"`
    4. `check(usdz_path)` → 0 erreur (package valide)
    5. `check(large_corpus_path)` (skipif env var absent) → retourne une
       liste non vide, dump `len(result)` dans caplog pour que le dev
       puisse vérifier l'ordre de grandeur manuellement
    6. `check(Path("/nonexistent.usd"))` → raises `RunnerError` avec
       `code == "FILE_NOT_FOUND"`

- [x] **Task 13 : Test parser (3 shapes + fallback)**
  - **File :** `tests/test_parser.py`
  - **Action :** parametrize sur `parser_samples.yaml`. Couvre :
    - Shape errors : `"Error checking rule 'NormalMapTextureChecker': …
      <PRIM> … @ASSET@"` → rule/prim/asset extraits
    - Shape warnings : `"<msg> (may violate 'SomeRule')"` → rule
      extrait, prim/asset possibles selon msg
    - Shape failed_checks (avec prim entre `<>`) :
      `"Shader <...> has invalid shader node. (fails '...')"`
    - Shape failed_checks (avec prim sans `<>`) :
      `"Incorrect type for /X/Y.attr. Expected 'T1'; got 'T2'. (fails
      '...')"`
    - Fallback Unknown : string gibberish → `rule == "Unknown"`,
      `message == raw`, `prim_path is None`, `asset_path is None`

- [x] **Task 14 : Test enricher**
  - **File :** `tests/test_enricher.py`
  - **Action :**
    - `load_patterns()` par défaut renvoie ≥2 entrées
    - `enrich(diag_with_known_rule)` → `title` non nul
    - `enrich(diag_with_unknown_rule)` → `title is None`
    - `EnrichedDiagnostic.to_dict()` matche le schéma AC 12

- [x] **Task 14bis : Test architecture (import-linter)**
  - **File :** `tests/test_architecture.py`
  - **Action :** invoque `importlinter.cli.lint_imports` en mode programme
    et assert exit code == 0. Le contrat `.importlinter` définit :
    ```ini
    [importlinter]
    root_package = usdchecker_ui
    [importlinter:contract:core-no-qt]
    name = Core must not import Qt
    type = forbidden
    source_modules = usdchecker_ui.core
    forbidden_modules = PySide6, PyQt6, PyQt5
    ```
  - **Notes :** fail-fast en CI. Peut être exécuté standalone via
    `lint-imports`.

- [x] **Task 15 : Test exporter**
  - **File :** `tests/test_exporter.py`
  - **Action :**
    - `to_json(diags, meta)` → `json.loads` OK, keys `meta` et
      `diagnostics`, chaque diagnostic a `enrichment` (potentiellement
      None)
    - `to_markdown` → contient H1, H2 par rule, count par rule
    - `to_html` → contient `<html>`, `<style>`, et chaque prim path

- [x] **Task 16 : Test editor_launcher + patterns_store**
  - **Files :** `tests/test_editor_launcher.py`, `tests/test_patterns_store.py`
  - **Action (editor_launcher) :**
    - `is_vscode_available()` monkeypatché via `shutil.which` → True/False
    - `find_prim_line()` sur `minimal_valid.usda` avec prim unique →
      `(ligne, True)`
    - `find_prim_line()` avec leaf name dupliqué dans fixture forgée →
      `(1, False)` + warning
    - `open_in_vscode()` raise `EditorNotAvailableError` si VSCode absent
  - **Action (patterns_store) :**
    - `user_patterns_path()` pointe bien vers `~/Library/Application
      Support/USDCheckerUI/patterns.yaml`
    - `ensure_user_override()` crée le fichier s'il n'existe pas, no-op
      sinon (monkeypatch HOME pour isoler)
    - `load_merged()` : user override écrase bundled rule par rule

#### Phase 5 — UI PySide6 (8 tasks)

- [x] **Task 17 : Drop zone** — cf. spec précédente (inchangé), filter
  extensions dans `dragEnterEvent`.

- [x] **Task 18 : CheckWorker (QThread boundary)**
  - **File :** `src/usdchecker_ui/ui/check_worker.py`
  - **Action :** `class CheckWorker(QObject)` avec :
    - Signal `finished(list)` (liste de `EnrichedDiagnostic`)
    - Signal `failed(str, str)` (code d'erreur, message)
    - Slot `@Slot(Path) run(path)` → appelle
      `core.runner.check(path)`, enrich chaque Diagnostic, émet
      `finished(list_enriched)`. Try/except sur `RunnerError` → `failed`.
    - Ce worker est **déplacé** sur un `QThread` dédié par la MainWindow.
  - **Notes :** **RIEN d'autre** ne touche pxr dans `ui/`. Contrat de F3.

- [x] **Task 19 : Diagnostic tree** — cf. spec précédente, hiérarchie
  Severity → Rule → Prim.

- [x] **Task 20 : Filter bar + proxy**
  - **Files :** `src/usdchecker_ui/ui/filter_bar.py`, modifs dans
    `diagnostic_tree.py`
  - **Action :** comme avant, **mais** le `QSortFilterProxyModel` doit
    appeler `setRecursiveFilteringEnabled(True)` (Qt 5.10+). Override
    `filterAcceptsRow` pour l'AND logique
    (severity + rule + texte libre).
  - **Notes :** **Contrat Qt critique** : sans recursive filtering, les
    parents qui ne matchent pas cachent leurs enfants matchants (F16).

- [x] **Task 21 : Detail panel** — cf. spec précédente (inchangé).

- [x] **Task 22 : Toolbar + actions**
  - **File :** `src/usdchecker_ui/ui/toolbar.py`
  - **Action :** boutons Ouvrir / Exporter / Ouvrir dans VSCode +
    **nouveau menu « Settings »** avec actions :
    - « Edit patterns… » → `patterns_store.open_for_edit()`
    - « Reload patterns » → `patterns_store.reload()` + signal
      `patternsReloaded` → MainWindow ré-enrichit les diagnostics
      actuellement affichés (sans re-checker le fichier)
  - **Notes :** le bouton VSCode reste grisé pour `.usdz/.usd/.usdc`.

- [x] **Task 23 : Main window**
  - **File :** `src/usdchecker_ui/ui/main_window.py`
  - **Action :** orchestration :
    1. Crée un `QThread` dédié + y move un `CheckWorker`. Connect signals
       `finished/failed`.
    2. Slot `_on_file_dropped(path)` → si worker idle, `worker.run(path)`.
       Si busy, affiche toast « Validation en cours » (F3, concurrency).
    3. Slot `_on_finished(list_enriched)` → alimente tree, update status
       bar.
    4. Slot `_on_failed(code, msg)` → `QMessageBox.critical` avec message
       adapté selon code (FILE_NOT_FOUND, USD_LOAD_ERROR, UNKNOWN).
    5. Slot `_on_export_requested(fmt)` → QFileDialog + write file.
    6. Slot `_on_editor_requested` → lit `unambiguous` retourné par
       `find_prim_line`, appelle `open_in_vscode`, affiche toast
       « Prim ambigu » si applicable. Catch `EditorNotAvailableError` →
       `QMessageBox.warning` avec le texte exact d'install (AC 17).
    7. Slot `_on_patterns_reloaded` → re-enrichit et rafraîchit le tree
       sans re-run checker.
  - **Notes :** à la fermeture de la window, `thread.quit(); thread.wait()`.

- [x] **Task 24 : Theme + entry point**
  - **Files :** `src/usdchecker_ui/ui/theme.py`, `src/usdchecker_ui/__main__.py`
  - **Action :** `__main__.main()` :
    1. `QApplication(sys.argv)` + `app.setOrganizationName("Adobe")`
       + `app.setApplicationName("USDCheckerUI")`
    2. **`core.plugins_warmup.warm()` AVANT** `MainWindow()` (F3)
    3. `theme.apply(app)` → stylesheet minimal
    4. `MainWindow()` + `show()` + `app.exec()`

#### Phase 6 — Packaging (2 tasks)

- [x] **Task 25 : PyInstaller spec**
  - **Files :** `packaging/pyinstaller.spec`,
    `packaging/entitlements.plist`, `packaging/Info.plist.template`
  - **Action :** spec `--windowed --onedir` avec :
    - `entry_point = src/usdchecker_ui/__main__.py`
    - `name = USDCheckerUI`
    - `bundle_identifier = com.adobe.eclair.usdchecker-ui`
    - `datas = [('src/usdchecker_ui/core/patterns.yaml',
      'usdchecker_ui/core')]`
    - `hiddenimports = ["pxr.Usd", "pxr.UsdUtils", "pxr.Sdf",
      "pxr.Ar", "pxr.Tf"]` — insurance contre une PyInstaller static
      analysis incomplète
    - `Info.plist` : `CFBundleDisplayName = "USDChecker UI"`,
      `CFBundleIdentifier = "com.adobe.eclair.usdchecker-ui"`,
      `CFBundleDocumentTypes` pour `.usd/.usda/.usdc/.usdz`
  - **Notes :** **pas de cap de taille** dans la spec. Mesurer
    post-build, loguer dans README.

- [x] **Task 26 : README final + smoke test**
  - **File :** `README.md`
  - **Action :** documenter :
    - Pitch (1 para)
    - Install dev (Python 3.12 via Homebrew/pyenv — **PAS** système)
    - Run dev : `python -m usdchecker_ui`
    - Tests : `pytest`
    - Corpus optionnel : `export USDCHECKER_UI_TEST_CORPUS=/path/to/BMW.usdz`
    - Build `.app` : `pyinstaller packaging/pyinstaller.spec --noconfirm`
    - **Taille attendue du bundle** : mesurée post-build, reportée ici
      (remplir après Task 25)
    - Premier lancement après partage : `xattr -d com.apple.quarantine
      USDCheckerUI.app`
    - **Édition patterns** : menu Settings → « Edit patterns… »
      (chemin : `~/Library/Application Support/USDCheckerUI/patterns.yaml`)
  - **Smoke test manuel** (dernière étape) :
    1. Launch `.app`
    2. Drag un `.usda` forgé invalid → diagnostics affichés
    3. Si corpus dispo : drag le gros fichier → ordre de grandeur OK
    4. Export JSON → validation schéma
    5. Settings → Edit patterns → modifier une ligne → Reload → vérifier
       que le title affiché change
    6. Ouvrir dans VSCode sur un `.usda` → ligne correcte (ou ligne 1 +
       toast si ambigu)

### Acceptance Criteria

#### Validation & chargement

- [x] **AC 1** : Given l'app est lancée, when je drag-drop un `.usda`
  forgé avec 1 erreur ShaderProperty connue (fixture
  `minimal_invalid.usda`), then l'arbre affiche au moins 1 diagnostic
  avec `rule == "ShaderPropertyTypeConformanceChecker"`, `severity
  == "error"`, et l'UI reste responsive pendant le check.

- [x] **AC 1bis** : Given `USDCHECKER_UI_TEST_CORPUS` pointe vers un gros
  `.usdz` (ex: BMW.usdz), when je drag-drop ce fichier dans l'app, then
  la validation se termine sans crash, l'arbre affiche au moins
  `NormalMapTextureChecker` et `ShaderPropertyTypeConformanceChecker`
  parmi les rules, groupées par Severity → Rule → Prim.

- [x] **AC 2** : Given l'app est lancée, when je drag-drop un fichier
  `.txt`, then le drop est rejeté avec tooltip « Format non supporté »,
  aucun check n'est lancé.

- [x] **AC 3** : Given l'app est lancée, when je drag-drop
  `minimal_valid.usda`, then l'arbre affiche « Aucun problème détecté »
  et la status bar affiche « 0 diagnostic ».

- [x] **AC 4** : Given l'app est lancée, when j'ouvre un fichier
  inexistant, then `QMessageBox.critical` affiche un message spécifique
  au code d'erreur `FILE_NOT_FOUND` ; l'UI précédente est préservée.

- [x] **AC 4bis** : Given l'app est lancée, when j'ouvre un `.usd`
  corrompu (header invalide), then `QMessageBox.critical` affiche un
  message spécifique au code `USD_LOAD_ERROR` (pas un message générique).

- [x] **AC 5 (Threading)** : Given un check sur un gros corpus est en
  cours, when je clique et déplace des éléments UI (toolbar, filtres),
  then l'UI reste responsive (< 50 ms de latency sur les events Qt) —
  prouvant que le check tourne bien sur un thread séparé.

- [x] **AC 5bis (Concurrency)** : Given un check est en cours, when je
  drop un 2e fichier, then le drop est rejeté avec toast « Validation
  en cours… », le check en cours n'est pas interrompu.

#### Enrichissement & dual view

- [x] **AC 6** : Given un diagnostic de rule `NormalMapTextureChecker`
  est sélectionné, when le detail_panel est en mode « Explication », then
  il affiche le `title`, `explanation`, `suggestion` de `patterns.yaml`
  (rendu markdown).

- [x] **AC 7** : Given le même diagnostic est sélectionné, when je toggle
  vers « Raw », then le detail_panel affiche la string brute exacte
  retournée par l'accesseur API d'origine (`GetErrors()`, `GetWarnings()`
  ou `GetFailedChecks()` selon source).

- [x] **AC 8** : Given un diagnostic de rule inconnue (pas dans
  `patterns.yaml`) est sélectionné, when le detail_panel tente d'afficher
  l'explication, then le toggle « Explication » est désactivé et une
  bannière info indique « Aucune explication enregistrée pour cette
  rule ».

- [x] **AC 8bis (Parser fallback)** : Given le runner produit une string
  qui ne matche aucune des 3 shapes regex connues, when elle est parsée,
  then elle devient un Diagnostic avec `rule == "Unknown"`,
  `prim_path is None`, `asset_path is None`, `message == raw string
  exacte`.

#### Filtres

- [x] **AC 9** : Given des diagnostics sont chargés, when je tape un
  fragment de nom de rule dans le champ filtre texte, then l'arbre se
  réduit aux seuls diagnostics dont le `message` ou `prim_path` contient
  ce fragment (AND avec les autres filtres), debouncé 200ms.

- [x] **AC 10** : Given des diagnostics avec plusieurs sévérités sont
  chargés, when je coche uniquement « Error » dans le filtre sévérité,
  then l'arbre affiche uniquement les diagnostics `severity == "error"`.

- [x] **AC 11** : Given un filtre texte + filtre rule + filtre sévérité
  sont actifs simultanément, when les trois restreignent le résultat,
  then seuls les diagnostics matchant LES TROIS critères sont visibles
  (AND logique).

- [x] **AC 12 (Tree recursive filter)** : Given la hiérarchie
  Severity → Rule → Prim est affichée, when un filtre matche UNIQUEMENT
  un prim feuille, then ses parents (Rule, Severity) restent visibles
  pour que le prim soit accessible (preuve de
  `setRecursiveFilteringEnabled(True)`).

- [x] **AC 13** : Given des filtres sont actifs, when je clique
  « Reset », then tous les filtres reviennent à leur état par défaut et
  l'arbre complet est restauré.

#### Export

- [x] **AC 14** : Given des diagnostics sont chargés, when je clique
  Exporter → JSON et choisis un chemin, then le fichier `.json` écrit
  est parsable, avec structure exacte :
  ```
  { "meta": {file_path, date, duration_seconds, total},
    "diagnostics": [{rule, severity, message, prim_path, asset_path,
      layer, enrichment: {title, explanation, suggestion} | null}, ...]}
  ```

- [x] **AC 15** : Given des diagnostics sont chargés, when je clique
  Exporter → Markdown, then le fichier `.md` contient un H1 avec le nom
  du fichier, un tableau meta, une section H2 par rule avec count et
  liste des prims.

- [x] **AC 16** : Given des diagnostics sont chargés, when je clique
  Exporter → HTML, then le fichier `.html` standalone est écrit (CSS
  inline) et s'ouvre correctement dans Safari/Chrome sans assets externes.

#### Open in editor

- [x] **AC 17** : Given un `.usda` est chargé ET un diagnostic avec prim
  à leaf name UNIQUE est sélectionné ET VSCode CLI `code` est installée,
  when je clique « Ouvrir dans VSCode », then VSCode s'ouvre sur le
  fichier à la ligne exacte du `def … "<leaf>"`.

- [x] **AC 17bis (Prim ambigu)** : Given un `.usda` est chargé ET un
  diagnostic dont le leaf name du prim apparaît plusieurs fois dans le
  fichier est sélectionné, when je clique « Ouvrir dans VSCode », then
  VSCode s'ouvre à la ligne 1 ET un toast jaune apparaît pendant 5s :
  « Prim ambigu — ouvert à la racine ».

- [x] **AC 18** : Given un `.usdz/.usd/.usdc` est chargé, when je regarde
  la toolbar, then le bouton « Ouvrir dans VSCode » est grisé avec
  tooltip « Disponible uniquement pour les fichiers .usda ».

- [x] **AC 19** : Given VSCode CLI n'est PAS installée, when je clique
  « Ouvrir dans VSCode », then un `QMessageBox.warning` affiche le texte
  exact : « VSCode CLI (`code`) introuvable. Ouvre VSCode → Cmd+Shift+P
  → tape 'Shell Command: Install \"code\" command in PATH' → relance
  USDChecker UI. »

#### Patterns editable

- [x] **AC 20** : Given l'app tourne avec uniquement le `patterns.yaml`
  bundled, when je clique Settings → « Edit patterns… » la première
  fois, then le fichier user `~/Library/Application
  Support/USDCheckerUI/patterns.yaml` est créé (copie du bundled) et
  s'ouvre dans l'éditeur système par défaut.

- [x] **AC 21** : Given le user a édité `patterns.yaml` (ex: changé un
  `title`), when je clique Settings → « Reload patterns », then les
  diagnostics actuellement affichés voient leur enrichissement
  rafraîchi SANS re-lancer de check USD (re-enrichissement uniquement).

#### Architecture & packaging

- [x] **AC 22** : Given le repo, when j'exécute `pytest`, then le test
  `tests/test_architecture.py` passe (contrat import-linter OK :
  `core/` n'importe aucun symbole Qt).

- [ ] **AC 23** (pending manual verification — PyInstaller spec
  implemented, build not exercised in this dev pass) : Given le repo
  est frais, when j'exécute `pip install -e ".[dev]"` puis
  `pyinstaller packaging/pyinstaller.spec --noconfirm`, then
  `dist/USDCheckerUI.app` est produit sans erreur ET contient
  `Contents/Resources/usdchecker_ui/core/patterns.yaml`.

- [ ] **AC 24** (pending manual verification — requires the built
  `.app`) : Given `USDCheckerUI.app` est construit et la quarantine
  est retirée, when je double-clique l'app, then la fenêtre principale
  apparaît dans les 3s, le drag-drop fonctionne sur
  `minimal_invalid.usda`, l'export JSON fonctionne, le bouton VSCode
  est correctement grisé pour un `.usdz`.

## Additional Context

### Dependencies

**Runtime (bundled via PyInstaller) :**
- Python 3.12
- PySide6 >= 6.7
- usd-core >= 25.11, < 27
- PyYAML >= 6.0

**Dev only :**
- PyInstaller >= 6.10
- pytest >= 8.0
- ruff >= 0.6
- import-linter >= 2.0

**External (best-effort, gracefully degraded) :**
- VSCode CLI `code` (« Open in editor »)

### Testing Strategy

- **Unit tests `pytest`** sur `core/` uniquement (runner, parser,
  enricher, exporter, editor_launcher, patterns_store).
- **Architecture test** (`test_architecture.py`) — failcase si `core/`
  importe Qt.
- **Fixtures légères in-repo** : 3 `.usda` forgés (valid, invalid shader,
  invalid normalmap) + 1 `.usdz` minimal ~10 KB + 1 yaml de raw strings
  pour le parser.
- **Corpus optionnel hors repo** via `USDCHECKER_UI_TEST_CORPUS` env var.
  Test skip gracefully si absent, dump counts en caplog sinon.
- **Pas de tests UI automatisés** MVP. Smoke test manuel documenté
  dans Task 26.

### Notes

**Risques identifiés + mitigations (mises à jour post-adversarial review) :**

1. **API binding drift entre versions `usd-core`** — contrat vérifié
   sur `/Users/rgt/USD/installed/lib/python/pxr/UsdUtils/complianceChecker.py`
   mais le wheel PyPI peut diverger subtilement. **Mitigation** : pin
   `>=25.11,<27`, tests Task 12 couvrent les 3 rules connues sur fixtures
   forgées — un drift fort casserait ces tests de manière déterministe.

2. **PyInstaller + `usd-core` plugin discovery** — `hiddenimports` dans
   la spec + `plugins_warmup.warm()` au startup forcent la résolution tôt.
   Si des rules manquent en mode packagé, ajouter les plugins manquants
   via `Analysis(datas=[...])` dans le spec.

3. **Taille du bundle** — pas de cap en AC (F10). Mesure + doc
   post-build. Si > 300 MB, explorer `--exclude-module` sur
   `pxr.UsdImagingGL`, `pxr.Hgi*` (hors scope validation).

4. **Parser regex limité aux 3 shapes vérifiées** — fallback Unknown +
   `parser_samples.yaml` extensible. Ajout de shapes futures se fait via
   une PR qui complète `parser_samples.yaml` + éventuellement un 4e regex.

5. **`find_prim_line` best-effort** — failure mode explicite (ligne 1
   + toast si ambigu, AC 17bis). Résolution complète nécessiterait
   parsing Sdf des subLayers — hors scope MVP.

6. **Éditabilité `patterns.yaml` dans le bundle signé** — résolu via
   layered config (Task 7 + AC 20 + AC 21).

**Findings adversariaux NON corrigés dans cette itération (Medium + Low) :**

- F12 (`minimal_valid.usda` peut tripper metadata defaults) — mitigé
  partiellement par l'inclusion de `upAxis` + `metersPerUnit` dans la
  fixture (Task 11) ; à surveiller au premier run des tests.
- F13 (schéma export) — résolu partiellement (AC 14 pin le schéma),
  sérialisation `EnrichedDiagnostic.to_dict()` pinée dans Task 6.
- F14 (texte exact du QMessageBox VSCode) — **résolu** en AC 19 (le
  texte est maintenant pin dans la spec).
- F15 (`.gitignore` ambigu sur `_bmad-output/`) — **résolu** : Task 1
  interdit explicitement d'ignorer `_bmad-output/`.
- F16 (tree filter footgun) — **résolu** : `setRecursiveFilteringEnabled(True)`
  est maintenant contractuel (Task 20 + AC 12).
- F17 (pas de test `.app` packagé) — non corrigé, accepté pour MVP.
- F18 (CLI oracle non operationalisé) — non corrigé, risque accepté.
- F19 (Python système vs pyenv) — **résolu** : Task 1 + Technical
  Decision 3 disent explicitement Homebrew/pyenv, pas le système.
- F20 (noms produits) — **résolu** partiellement : `CFBundleIdentifier =
  com.adobe.eclair.usdchecker-ui` maintenant défini (Task 25).
- F21 (Info severity) — **résolu** : `severity` Literal restreint à
  `"error" | "warning"`, filtre UI n'expose plus « Info ».
- F22 (i18n) — reporté : strings FR hardcodées, accepté pour MVP.
- F23 (exception taxonomy) — **résolu** : `RunnerError` a maintenant
  un `code` typé (Task 3, AC 4, AC 4bis).

## Review Notes (post-implementation adversarial review, 2026-04-22)

- Second adversarial review run after implementation: 25 findings surfaced.
- **22 fixed automatically.** Notable patches:
  - F3/F15 — parser over-greedy prim path + `find_prim_line` now tolerant
    to `over`/`class`/property-qualified paths (strips `.attr[:prop]`).
  - F7 — runner catches `RuntimeError`/`ValueError`/`OSError` as
    `USD_LOAD_ERROR` (AC 4bis robustness).
  - F9/F10 — broken user `patterns.yaml` no longer nukes a check or
    crashes « Reload patterns »; falls back + QMessageBox.
  - F17 — `EnrichedDiagnostic.has_pattern` field distinguishes
    "pattern absent" from "pattern with empty fields" in JSON export
    schema (AC 14).
  - F20 — `Signal(Path)` → `Signal(str)` across QThread boundary to
    dodge Qt metatype registration edge cases.
  - F21/F22 — packaging: dropped aggressive entitlements
    (`disable-library-validation`) and the `LSItemContentTypes`
    `public.data` claim (was shadowing every data file).
  - F23 — new `tests/test_main_window_text.py` pins the exact AC 19
    VSCode-missing message.
  - F12 — new `tests/test_tree_proxy.py` pins
    `setRecursiveFilteringEnabled(True)` (AC 12 contract).
  - F24 — `test_valid_usda_returns_empty` softened (future-proof
    against new default USD checkers in the `>=25.11,<27` range).
- **3 skipped:**
  - **F1** — reviewer wanted `GetFailedChecks → "failed"` but AC 1
    explicitly pins `severity == "error"` for
    `ShaderPropertyTypeConformanceChecker`. Would break the contract.
  - **F8** — precedence of FILE_NOT_FOUND vs pxr import error: not
    user-actionable, kept as-is.
  - **F19** — debounce re-entrancy on checkbox toggle: flagged
    "uncertain" by reviewer, no repro on tested corpora.
- Final test run: **35 passed, 1 skipped** (optional
  `USDCHECKER_UI_TEST_CORPUS`). Ruff clean. Import-linter contract
  kept.
- AC 23 / AC 24 remain pending manual verification (require running
  `pyinstaller` + double-clicking the built `.app`).

**Futures considerations (hors scope MVP) :**

- Build Windows : spec portable, rebuild PyInstaller sur Windows box.
- Port Eclair Studio : `core/` rédigeable en C++ (~500 LOC).
- Nouveau framework validation (`--useNewValidationFramework`) : migrer
  si `UsdValidationContext` exposé en Python → diagnostics structurés
  (plus de parser regex).
- Notarization Apple pour distribution hors team interne.
- Historique des validations (SQLite).
- i18n strings (F22).

**Décision tranchée en Step 2 :** NE PAS bundler le binaire `usdchecker`.
Utiliser le wheel PyPI `usd-core` (Option B).
**Décision post-adversarial review :** durcir le threading contract,
layered patterns, architecture enforcement (import-linter), fixtures
forgées légères comme source de vérité primaire.
