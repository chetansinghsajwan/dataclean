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
| `catalog_types` | `list[type[Catalog]]` | `[]` | Each path scheme belongs to one catalog; registering a duplicate scheme raises `ValueError` — see [Plugins](plugins.md). |
| `presets` | `list[Preset]` | `[]` | See the [Preset note](plugins.md#preset-scaffolding-only) — not consumed anywhere yet. |
| `catalog` | `Catalog \| None` | `None` | An explicit default catalog for `clean_paths()`. |
| `inplace` | `bool` | `True` | Declared global default; not currently read by `clean_paths()` (see below). |

`Config.__post_init__` auto-registers exactly these 13 of the 14 exported cleaners:
`AddressCleaner`, `BoolCleaner`, `CountryCleaner`, `DateTimeCleaner`, `EmailCleaner`,
`FilePathCleaner`, `GenderCleaner`, `NameCleaner`, `NumericCleaner`, `PhoneCleaner`, `TextCleaner`,
`UrlCleaner`, `UuidCleaner`. `EnumCleaner` needs a `cases=` argument, so there's no sensible default
— register it yourself (see
[Getting Started](getting-started.md#whats-registered-out-of-the-box)).

### Registering things

```python
from dataclean import config

config.register_cleaner(my_cleaner_instance)  # appends if not already present
config.register_dataframe(MyDataFrameAdapter)  # a type, not an instance
config.register_catalog(MyCatalog)  # raises if a scheme is already taken
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

`clean_paths()` resolves catalogs as follows. An explicit `catalog=` (an
instance, or the class name of a registered type) handles every path, as
does `config.catalog` when `use_global_config=True`; no prefixes are parsed
in that case. Otherwise each path is routed by its scheme prefix
(`scheme:rest`) to the registered catalog that lists that scheme, and
unprefixed paths go to the catalog that lists `""`. An unknown scheme raises
`ValueError`.

`inplace` is accepted and logged but is not yet threaded into the cleaning
pipeline. `dry_run` skips the actual read and write calls while still expanding
paths, mapping write paths and logging, which is useful for previewing what a
run would touch.

### Path patterns

`paths` accepts literal paths, globs and regexes. A literal path is passed
through without checking that it exists. A regex is written `re:<regex>` and
must match the whole path.

| Catalog | Glob | Regex |
|---|---|---|
| Local (`pandas`, `ibis`) | `*`, `?`, `[...]`, `**` for any depth, files only | `re:data/report_\d+\.csv`, matched against the path written with `/`, searching below the regex's literal leading directory (or the working directory) |
| Unity (`databricks`) | `*` and `?` in each of `catalog.schema.table` (missing parts mean `*`) | `re:prod\.raw\.cust_\d+`, matched against the full `catalog.schema.table` name with `RLIKE` |

Unity patterns reach the metastore only as bound query parameters, and `_` and
`%` in a name are matched literally.

### Choosing the cleaner for a column

Detection picks a cleaner for each column from its name and values.
`column_cleaners` overrides it for the columns you name (CLI: `--col
COLUMN=CLEANER`, repeatable). A cleaner is given by its registered name, such
as `"EmailCleaner"`, or as an instance, which is how an `EnumCleaner` with
`cases=` is used. An unknown name raises `ValueError`. A column that a dataset
does not have is skipped, so one mapping can cover many datasets. In
`clean_paths()` and the CLI the name is the column's name after renaming.

To leave a column alone, use `ignore_cols` (CLI: `--ignore-col`). It wins over
`column_cleaners`. `clean()` takes both options too.

```python
dataclean.clean_paths(
    paths=["prod.raw.*"],
    column_cleaners={"contact": "EmailCleaner"},
    ignore_cols=["notes"],
)
```

```bash
dataclean clean "prod.raw.*" --col contact=EmailCleaner --ignore-col notes
```

### Keeping the original values

`keep_original=True` (CLI: `--keep-original`) keeps the raw values of every
column that a cleaner overwrites in place, as a copy named `<column>_uncleaned`
(change it with `original_suffix=` or `--original-suffix`). The copy is taken
before any cleaner runs. Columns that a cleaner only adds new columns for, such
as the address parts, are not copied, since the original is still there. If a
copy's name is already a column, a `PipelineConfigError` is raised. `clean()`
and `Pipeline` take the same two options.

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
