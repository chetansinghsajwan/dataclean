# Configuration

## The global `Config` singleton

`dataclean.config.config` (`src/dataclean/config.py`) is a single mutable
`Config` instance created at import time. `clean()`, `clean_paths()`, and the
default `Pipeline` construction all read from it unless you build your own
`Pipeline` explicitly.

| Field | Type | Default | Notes |
|---|---|---|---|
| `ignore_cols` | `list[str]` | `[]` | Column names to skip during cleaning. |
| `cleaners` | `list[Cleaner]` | 10 built-in instances | See below — everything except `EnumCleaner`. |
| `col_renamer` | `ColRenamer` | `ColRenamer(case="snake")` | Default column-name normalizer. |
| `plugin_loader` | `PluginLoader \| None` | `PluginLoader()` | `None` disables plugin auto-loading entirely. |
| `dataframe_apis` | `list[type[DataFrame]]` | `[]` | Empty until a plugin registers one. |
| `auto_load_plugins` | `bool` | `True` | If `True`, `clean()`/`clean_paths()` call `plugin_loader.load_plugins()` first. |
| `catalog_types` | `list[type[Catalog]]` | `[]` | Kept sorted by descending `priority` — see [Plugins](plugins.md). |
| `presets` | `list[Preset]` | `[]` | See the [Preset note](plugins.md#preset-scaffolding-only) — not consumed anywhere yet. |
| `catalog` | `Catalog \| None` | `None` | An explicit default catalog for `clean_paths()`. |
| `inplace` | `bool` | `True` | Declared global default; not currently read by `clean_paths()` (see below). |

`Config.__post_init__` auto-registers exactly these 10 of the 11 exported
cleaners: `AddressCleaner`, `BoolCleaner`, `CountryCleaner`,
`DateTimeCleaner`, `EmailCleaner`, `GenderCleaner`, `NumericCleaner`,
`PhoneCleaner`, `TextCleaner`, `UuidCleaner`. `EnumCleaner` needs a `cases=`
argument, so there's no sensible default — register it yourself (see
[Getting Started](getting-started.md#whats-registered-out-of-the-box)).

### Registering things

```python
from dataclean import config

config.register_cleaner(my_cleaner_instance)  # appends if not already present
config.register_dataframe(MyDataFrameAdapter)  # a type, not an instance
config.register_catalog(MyCatalog)  # kept sorted by descending priority
config.register_preset(my_preset_instance)
```

::: dataclean.config.Config

## `ColRenamer`

`ColRenamer` (`src/dataclean/col_renamer.py`) normalizes column names into a
consistent case. It splits each name into words with `wordninja` (so it can
split concatenated names like `"firstname"` into `("first", "name")`) and
rejoins them per the chosen case.

```python
from dataclean import ColRenamer

renamer = ColRenamer(case="snake")
renamer.rename_cols(["FirstName", "e-mail", "PhoneNumber"])
# -> {"FirstName": "first_name", "e-mail": "e_mail", "PhoneNumber": "phone_number"}
# (only entries that actually change are included)

renamer.rename("FirstName")  # -> "first_name" (always returns a value)
```

Available `case` values: `snake`, `upper_snake`, `upper`, `lower` (default if
omitted), `pascal`, `camel`, `kebab`, `train`, `cobol`.

## `clean()` vs `clean_paths()`

| | `clean(df, auto_detect=True)` | `clean_paths(paths, ...)` |
|---|---|---|
| Input | An already-loaded dataframe object | Path patterns expanded via a `Catalog` |
| Use when | You already have data in memory | Cleaning tables/files at rest |
| Cleaners used | `config.cleaners`, `auto_detect` as passed | Always `config.cleaners` with `auto_detect=True` |
| Output | Returns the cleaned `DataFrame` | Reads, cleans, and writes each expanded path; returns a `CleanPathResult` |

`clean_paths()` resolves its `catalog` in order: the explicit `catalog=`
argument, then `config.catalog` (if `use_global_config=True`), then the
first registered `catalog_types` entry (tried in descending-priority order)
whose `supports_env()` returns `True` and `instantiate()` succeeds. If none
resolves, it raises `ValueError("catalog must be provided")`.

!!! warning "Several `clean_paths()` parameters are accepted but not yet wired in"
    `rename_cols`, `rename_col_map`, `col_renamer`, `clean_cols`,
    `ignore_cols`, `inplace`, and `cleaners` are all accepted by
    `clean_paths()` and logged for diagnostics, but **do not currently affect
    cleaning behavior** — cleaning always runs `config.cleaners` with
    `auto_detect=True` regardless of what you pass for these. This is
    documented directly in the function's own docstring, not a doc-writing
    guess. `dry_run` *is* implemented: it skips the actual read/write calls
    while still expanding paths, mapping write paths, and logging as normal
    — useful for previewing what a run would touch.

```python
import dataclean

result = dataclean.clean_paths(
    paths=["prod.raw.customers"],
    write_path="prod.prep.*",
    dry_run=True,  # preview only — no reads/writes happen
)
```

::: dataclean.clean.clean

::: dataclean.clean.clean_paths
