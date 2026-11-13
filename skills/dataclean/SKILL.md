---
name: dataclean
description: Clean messy tabular data with the dataclean Python package. Use when a pandas, ibis or PySpark/Databricks dataframe, or a set of files or Unity Catalog tables, has dirty emails, phone numbers, countries, dates, names, addresses, booleans or similar columns that need normalising.
---

# dataclean

`dataclean` picks a cleaner for each column from its name and values and fixes
the values in place. Use it instead of writing per-column regex.

## Setup

Install the core package and the plugin for the dataframe library. Without a
plugin, `clean()` raises `TypeError`, because no engine supports the dataframe.
The packages are not on PyPI yet, so install from GitHub (`uv add` in a uv
project, `pip install` otherwise). Plugins live in `plugins/` of the same repo:

```sh
uv pip install "dataclean @ git+https://github.com/chetansinghsajwan/dataclean"
uv pip install "dataclean-pandas @ git+https://github.com/chetansinghsajwan/dataclean#subdirectory=plugins/dataclean-pandas"
```

For PySpark and Unity Catalog, use `plugins/dataclean-databricks`.

Once published, this becomes `pip install dataclean dataclean-pandas`.

## Clean a dataframe

```python
import dataclean

result = dataclean.clean(df)
cleaned = result.df  # your own dataframe type, inside the wrapper
```

- `clean()` returns a wrapper, not your dataframe type. Use `.df`.
- Detection uses the column name too. `email`, `phone`, `country` are
  detected; `e-mail` or `Contact Info` may not be. Rename columns first, or
  force the cleaner.
- `keep_original=True` keeps raw values as `<column>_uncleaned` (change the
  suffix with `original_suffix=`). A name clash raises `PipelineConfigError`.
- `auto_detect=False` runs no detection, so only `column_cleaners` apply.

## Clean files or tables at rest

```python
dataclean.clean_paths(
    ["data/raw/*.csv"],  # glob, or "re:<regex>" matching the full path
    write_path="data/clean/*.csv",  # template, * is filled from the input path
)
```

- Columns are renamed to snake case first (`rename_cols=False` to stop,
  `rename_col_map={"old": "new"}` to force).
- A scheme prefix picks the catalog: `path:`/`pandas:`/none for local files,
  `ibis:`, `databricks:` for Unity Catalog (`catalog.schema.table`, `*` and `?`
  allowed in each part). An unknown scheme raises `ValueError`.
- `dry_run=True` expands paths and writes nothing. Use it before a big run.
- Writing to an existing Unity Catalog table fails.

Same from the shell:

```sh
dataclean clean "data/raw/*.csv" "data/clean/*.csv" --catalog pandas --dry-run
```

## Override the cleaners

```python
dataclean.clean(
    df,
    column_cleaners={"contact": "EmailCleaner"},  # by registered name or instance
    ignore_cols=["notes"],  # wins over column_cleaners
)
```

CLI: `--col contact=EmailCleaner` and `--ignore-col notes`, both repeatable.
In `clean_paths()` and the CLI, use the column name after renaming. An unknown
cleaner name raises `ValueError`. A column a dataset lacks is skipped.

`clean_paths(cleaners=["EmailCleaner", ...])` restricts which cleaners may be
auto-detected.

## Cleaners

Registered by default: `AddressCleaner`, `BoolCleaner`, `CountryCleaner`,
`DateTimeCleaner`, `EmailCleaner`, `FilePathCleaner`, `GenderCleaner`,
`NameCleaner`, `NumericCleaner`, `PhoneCleaner`, `TextCleaner`, `UrlCleaner`,
`UuidCleaner`.

`EnumCleaner` is explicit-only, because it needs `cases=`:

```python
from dataclean import EnumCleaner

dataclean.clean(
    df,
    column_cleaners={
        "status": EnumCleaner(
            cases={"active": ["active", "1"], "inactive": ["inactive", "0"]}
        )
    },
)
```

Some cleaners add columns instead of overwriting (for example the address
cleaner writes parts such as street and house number). Their input is kept.

## Gotchas

- Do not call a cleaner on a column by hand; go through `clean()`.
- Cleaners are frozen and configured at construction. Build a new instance to
  change an option.
- Do not depend on `PandasDataFrame` or `PysparkDataFrame` internals; use the
  `DataFrame` interface.
- Cleaner details and options: `docs/cleaners.md` in the repo.
