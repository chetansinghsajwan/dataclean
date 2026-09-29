# Getting Started

## Install

`dataclean` on its own only gives you the `Cleaner` implementations and the
`Pipeline`/`Config` machinery — it does not know how to read a pandas
`DataFrame` or a PySpark one until a matching engine plugin is installed.
`Config.__post_init__` (`src/dataclean/config.py`) pre-registers cleaners
only; `dataframe_apis` and `catalog_types` both start empty.

**Working inside this repo** (the devbox + `uv` monorepo): the engine plugins
under `plugins/` (`dataclean-pandas`, `dataclean-databricks`, ...) are
declared as editable dev dependencies in `pyproject.toml`'s
`[tool.uv.sources]`. Running the standard setup task installs everything you
need:

```sh
task setup
```

**Consuming `dataclean` as a standalone package**: install the core package
plus whichever engine adapter matches your dataframe library, e.g.:

```sh
uv add dataclean dataclean-pandas
```

## Your first `clean()` call

```python
import pandas as pd
import dataclean

df = pd.DataFrame({
    "email": [" User@Example.com "],
    "phone": ["9876543210"],
    "country": ["IN"],
})

cleaned = dataclean.clean(df)
```

`clean()` (`src/dataclean/clean.py`) does three things:

1. If `dataclean.config.config.auto_load_plugins` is `True` (the default),
   it loads every installed `dataclean-*` plugin — this is what registers a
   `PandasDataFrame`/`PysparkDataFrame` adapter (and any `Catalog`s the
   plugin ships) into the global `Config`. You don't need to call anything
   yourself for this to happen.
2. It builds a `Pipeline(cleaners=config.cleaners, auto_detect=True)`.
3. It calls `pipeline.fit_transform(df)` and returns the result.

See [Concepts](concepts.md) for exactly how `fit_transform` decides which
cleaner applies to which column.

## What's registered out of the box

`Config.__post_init__` auto-registers 10 of the 11 cleaners exported from
`dataclean`:

`AddressCleaner`, `BoolCleaner`, `CountryCleaner`, `DateTimeCleaner`,
`EmailCleaner`, `GenderCleaner`, `NumericCleaner`, `PhoneCleaner`,
`TextCleaner`, `UuidCleaner`.

`EnumCleaner` is **not** auto-registered — it requires a `cases=` argument at
construction time, so there's no sensible default to register. Use it by
constructing and registering it yourself:

```python
from dataclean import config, EnumCleaner

config.register_cleaner(
    EnumCleaner(cases={"active": ["active", "1"], "inactive": ["inactive", "0"]})
)
```

Full details on every cleaner (constructor options, expected input/output,
and known gotchas) are in [Built-in Cleaners](cleaners.md).

## Cleaning data at rest instead of an in-memory dataframe

If you're cleaning tables/files discovered through a `Catalog` rather than
an already-loaded dataframe, see `clean_paths()` in
[Configuration](configuration.md#clean-vs-clean_paths).
