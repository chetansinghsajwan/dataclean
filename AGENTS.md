# AGENTS.md

## 1. Project Context & Environment

- **Environment:** Run all commands inside the configured `devbox shell` (via
  Devbox). Do not run commands on the local host outside Devbox.
- **Python Package Manager:** `uv`
- **Python Version:** 3.12 managed via `uv`.
- **Primary Tooling:** Ruff (Linting & Formatting), Pytest (Testing)

## 2. Project Design

- **Cleaning Architecture:** Cleaning is handled by cleaners.
- **The Base Class:** There is a single base class for all cleaners called
  `Cleaner`, defined in `src/dataclean/cleaners/cleaner.py`.
- **Immutability & Compilation:** The cleaner is always frozen and follows the
  design that configuration is provided during cleaner object creation. All
  prerequisite calculations and type validation are done exactly once during
  creation. During runtime (e.g., in `clean_row`), repeated code and condition
  branching overhead must be avoided as much as possible.
- **Engine Abstraction:** Data manipulation is handled by data engines.
- **The DataFrame Interface:** There is a base class for dataframes of engines
  called `DataFrame`, defined in `src/dataclean/engine/dataframe.py`.
- **Implementation Decoupling:** Concrete data engine implementations (e.g.
  `PandasDataFrame`, `PysparkDataFrame`) live in separate installable plugin
  packages under `plugins/` (e.g. `plugins/dataclean-pandas`,
  `plugins/dataclean-databricks`), not in `src/dataclean` itself. Never depend
  directly on the underlying implementation; always manipulate data strictly
  using the `DataFrame` interface.
- **Plugins:** A plugin is any installed Python distribution named
  `dataclean-*` that exposes a module-level `info` attribute
  (`PluginInfo`). Plugins are discovered and registered at runtime by
  `src/dataclean/plugins/loader.py`. Data engine adapters and integrations
  (e.g. `dataclean-cch-crm`) are both implemented as plugins.
- **Pipeline Orchestration:** `Pipeline` (`src/dataclean/pipeline/pipeline.py`)
  is the orchestrator that resolves which `Cleaner` applies to which column
  and runs them over a `DataFrame`; it composes `Resolver`
  (`cleaner_resolver.py`), `DependencyResolver`, `EntityExtractor`, and
  `Assignment`. It is the layer underneath the public `clean()` /
  `clean_paths()` entrypoints (`src/dataclean/clean.py`).
- **Presets:** `Preset` (`src/dataclean/preset/__init__.py`) is the abstract
  base for reusable, matchable bundles of cleaners: subclasses score how well
  they fit a dataframe's columns (`match`) and propose a cleaner assignment
  for them (`get`).
- **Column Renaming:** `ColRenamer` (`src/dataclean/col_renamer.py`) splits
  and re-joins column names into a consistent casing convention (snake_case,
  camelCase, etc.), using `wordninja` to split concatenated names.
- **Catalogs:** `Catalog` (`src/dataclean/engine/catalog.py`) discovers,
  reads, and writes cataloged data paths for `clean_paths`; concrete catalogs
  live alongside each engine plugin.

## 3. Tooling & Execution Commands

Always use the `Taskfile.yml` tasks through Devbox for routine project commands
such as setup, formatting, checks, fixes, and tests. Do not call the underlying
tools directly when an equivalent Taskfile task exists.

- **Environment Setup:** `task setup` (Installs all dependencies and sets up
  the virtual environment via Devbox + uv).
- **Format all supported files:** `task fmt`
- **Check all supported files:** `task check`
- **Apply safe fixes:** `task fix`
- **Apply unsafe fixes:** `task fix:unsafe` (requires explicit user approval,
  because it may change behavior).
- **Run all tests:** `task test`
- **Run cleaner or engine tests:** `task test:cleaners` (core cleaners),
  `task test:pandas` (pandas engine plugin), or `task test:pyspark`
  (PySpark/Databricks engine plugin).
- **Run a targeted test task:** use the named tasks such as `task test:phone`,
  `task test:email`, or `task test:country`.
- **Add Dependency:** `uv add <package_name>`
- **Add Dev Dependency:** `uv add --dev <package_name>`

### Task subcommands and file targeting

Use the language-specific Taskfile commands below. For commands that accept
paths, pass them after `--` with whitespace separation, for example
`task fmt:py -- filepath.py filepath2.py`—never comma-separate paths.

| Files | Format | Check | Safe fix | Standard input |
| --- | --- | --- | --- | --- |
| YAML | `task fmt:yaml` | `task check:yaml` | `task fix:yaml` | `task fmt:yaml:stdio` |
| TOML | `task fmt:toml` | `task check:toml` | `task fix:toml` | `task fmt:toml:stdio` |
| Markdown | `task fmt:md` | `task check:md` | `task fix:md` | `task fmt:md:stdio` |
| Shell/Bash | `task fmt:sh` | `task check:sh` | `task fix:sh` | `task fmt:sh:stdio` |
| JSON/JSONC | `task fmt:json` | `task check:json` | `task fix:json` | `task fmt:json:stdio` |
| Python (`.py`, `.pyi`, `.ipynb`) | `task fmt:py` | `task check:py` | `task fix:py` | `task fmt:py:stdio` |
| Nix | `task fmt:nix` | `task check:nix` | `task fix:nix` | `task fmt:nix:stdio` |
| GitHub Actions | — | `task check:gha` | — | — |

- All format, check, and fix tasks other than TOML accept specific paths after
  `--`; their default target is the repository root. `task fmt:toml`,
  `task check:toml`, and `task fix:toml` operate on the project’s TOML files.
- `task fix:py:unsafe` applies Python unsafe fixes and prompts because they can
  change behavior; obtain explicit user approval before using it.
- There is no generic `task fmt:stdio`; stdin tasks are language-specific, as
  listed above.

Safe, in-scope commands—including reading files, formatting, linting, and
testing—do not require asking the user for permission. Ask only before commands
that are destructive, need elevated access, or create a meaningful external
side effect.

### Git Hooks (Lefthook)

- **Pre-commit:** Automatically runs the relevant `task fmt:*` for each
  staged file's type and re-stages the fixed result. Manually running
  `task fmt` before committing is not required, but doing so surfaces
  issues earlier.
- **Pre-push:** Automatically runs `task check` (all linters, including
  `ty check`). A push is rejected if `task check` fails, so treat it as
  a hard gate—resolve failures rather than pushing around them.

## 4. Strict Guardrails & Code Conventions

### Typing & Guardrails (Non-Negotiable)

- **Strict Typing:** Every function signature MUST include explicit type hints
  for all parameters and return values (e.g.,
  `def get_user(user_id: int) -> User | None:`).
- **No Any:** Do not use `Any` types. If a type is genuinely dynamic, utilize
  structural subtyping via `Protocol`, generic type variables (`TypeVar`), or a
  clean `Union`.
- **Validation:** Always execute the strict type check command (`ty check`,
  run via `task check:py` or `task fix:py`) before marking a feature or file
  change as complete. Zero type errors are permitted.
- **Runtime Type Checking:** Static hints alone are not enough—decorate
  public functions, dataclasses, and ABCs with `@checked` (from
  `dataclean.types`) so `beartype` validates arguments, return values, and
  (for `@dataclass`) fields against their type hints at call/construction
  time. Place `@checked` above `@dataclass` so it wraps the generated
  `__init__`. Use `@dev_checked` instead only for checks that should be
  compiled out in production (it is a no-op unless `APP_ENV=dev`).

### Code Quality & Refactoring

- **Ruff Compliance:** Ensure all code adheres to the rules defined in
  `pyproject.toml`. Let `ruff check --fix` handle auto-fixable errors before
  writing code manually.
- **Test Invariants:** All new logic must be accompanied by matching unit or
  integration tests in the `/tests` directory. Mock external API calls strictly
  using `pytest-mock`.
- **State & Scope:** Prefer pure functions and immutable data structures (like
  Pydantic v2 models or frozen dataclasses) to minimize side effects.

### Local Guardrails

- **File System:** Do not modify the `devbox.json` / `devbox.lock`
  configurations unless explicitly instructed.
- **Lockfiles:** Never manually edit `uv.lock`. Always let `uv` handle lockfile
  updates through standard CLI commands.
