# AGENTS.md

## 1. Project Context & Environment

- **Environment:** Run all commands inside the configured `devbox shell` (via Devbox). Do not run commands on the local host outside Devbox.
- **Python Package Manager:** `uv`
- **Python Version:** 3.12 managed via `uv`.
- **Primary Tooling:** Ruff (Linting & Formatting), Pytest (Testing)

## 2. Project Design

- **Cleaning Architecture:** Cleaning is handled by cleaners.
- **The Base Class:** There is a base class for all cleaners called `BaseCleaner`.
- **Immutability & Compilation:** The cleaner is always frozen and follows the design that configuration is provided during cleaner object creation. All prerequisite calculations and type validation are done exactly once during creation. During runtime (e.g., in `clean_value`), repeated code and condition branching overhead must be avoided as much as possible.
- **Engine Abstraction:** Data manipulation is handled by data engines.
- **The DataFrame Interface:** There is a base class for dataframes of engines called `DataFrame`.
- **Implementation Decoupling:** There are concrete data engine implementations like `PandasDataFrame` and `PysparkDataFrame`. Never depend directly on the underlying implementation; always manipulate data strictly using the `DataFrame` interface.

## 3. Tooling & Execution Commands

Always execute commands exactly as formatted below to prevent lockfile or environment drift:

- **Environment Setup:** `devbox run task setup` (Installs all dependencies and sets up the virtual environment via Devbox + uv).
- **Add Dependency:** `uv add <package_name>`
- **Add Dev Dependency:** `uv add --dev <package_name>`
- **Run Linter (Ruff):** `uv run ruff check . --fix`
- **Run Formatter (Ruff):** `uv run ruff format .`
- **Execute All Tests:** `uv run pytest`
- **Execute Single Test File:** `uv run pytest <path_to_test_file>.py -v`

## 4. Strict Guardrails & Code Conventions

### Typing & Guardrails (Non-Negotiable)

- **Strict Typing:** Every function signature MUST include explicit type hints for all parameters and return values (e.g., `def get_user(user_id: int) -> User | None:`).
- **No Any:** Do not use `Any` types. If a type is genuinely dynamic, utilize structural subtyping via `Protocol`, generic type variables (`TypeVar`), or a clean `Union`.
- **Validation:** Always execute the strict type check command (`uv run mypy . --strict`) before marking a feature or file change as complete. Zero type errors are permitted.

### Code Quality & Refactoring

- **Ruff Compliance:** Ensure all code adheres to the rules defined in `pyproject.toml`. Let `ruff check --fix` handle auto-fixable errors before writing code manually.
- **Test Invariants:** All new logic must be accompanied by matching unit or integration tests in the `/tests` directory. Mock external API calls strictly using `pytest-mock`.
- **State & Scope:** Prefer pure functions and immutable data structures (like Pydantic v2 models or frozen dataclasses) to minimize side effects.

### Local Guardrails

- **File System:** Do not modify the `devbox.json` / `devbox.lock` configurations unless explicitly instructed.
- **Lockfiles:** Never manually edit `uv.lock`. Always let `uv` handle lockfile updates through standard CLI commands.
