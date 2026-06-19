# AGENTS.md

## 1. Project Context & Environment

- **Environment:** Run all commands inside the configured `.devcontainer`. Do not run commands on the local host.
- **Python Package Manager:** `uv`
- **Python Version:** 3.12 managed via `uv`.
- **Primary Tooling:** Ruff (Linting & Formatting), Pytest (Testing)

## 2. Tooling & Execution Commands

Always execute commands exactly as formatted below to prevent lockfile or environment drift:

- **Environment Setup:** `uv sync` (Installs all dependencies and sets up the virtual environment).
- **Add Dependency:** `uv add <package_name>`
- **Add Dev Dependency:** `uv add --dev <package_name>`
- **Run Linter (Ruff):** `uv run ruff check . --fix`
- **Run Formatter (Ruff):** `uv run ruff format .`
- **Execute All Tests:** `uv run pytest`
- **Execute Single Test File:** `uv run pytest <path_to_test_file>.py -v`

## 3. Strict Guardrails & Code Conventions

### Typing & Guardrails (Non-Negotiable)

- **Strict Typing:** Every function signature MUST include explicit type hints for all parameters and return values (e.g., `def get_user(user_id: int) -> User | None:`).
- **No Any:** Do not use `Any` types. If a type is genuinely dynamic, utilize structural subtyping via `Protocol`, generic type variables (`TypeVar`), or a clean `Union`.
- **Validation:** Always execute the strict type check command (`uv run mypy . --strict`) before marking a feature or file change as complete. Zero type errors are permitted.

### Code Quality & Refactoring

- **Ruff Compliance:** Ensure all code adheres to the rules defined in `pyproject.toml`. Let `ruff check --fix` handle auto-fixable errors before writing code manually.
- **Test Invariants:** All new logic must be accompanied by matching unit or integration tests in the `/tests` directory. Mock external API calls strictly using `pytest-mock`.
- **State & Scope:** Prefer pure functions and immutable data structures (like Pydantic v2 models or frozen dataclasses) to minimize side effects.

### Local Guardrails

- **File System:** Do not modify the `.devcontainer/` configurations unless explicitly instructed.
- **Lockfiles:** Never manually edit `uv.lock`. Always let `uv` handle lockfile updates through standard CLI commands.
