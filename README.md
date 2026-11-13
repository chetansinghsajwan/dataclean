# dataclean

[![Tests](https://github.com/chetansinghsajwan/dataclean/actions/workflows/tests.yml/badge.svg)](https://github.com/chetansinghsajwan/dataclean/actions/workflows/tests.yml)
[![Release](https://github.com/chetansinghsajwan/dataclean/actions/workflows/release.yml/badge.svg)](https://github.com/chetansinghsajwan/dataclean/actions/workflows/release.yml)
[![pages-build-deployment](https://github.com/chetansinghsajwan/dataclean/actions/workflows/pages/pages-build-deployment/badge.svg)](https://github.com/chetansinghsajwan/dataclean/actions/workflows/pages/pages-build-deployment)
[![Built with Devbox](https://www.jetify.com/img/devbox/shield_moon.svg)](https://www.jetify.com/devbox/docs/contributor-quickstart/)

Automatic cleaning of messy tabular data. `dataclean` looks at each column's
name and values, picks a cleaner for it (email, phone, country, date, name,
address and more), and fixes the values in place. It runs on pandas, ibis and
PySpark (Databricks) through small engine plugins.

## Install

`dataclean` is not on PyPI yet, so install it straight from GitHub. The core
package has the cleaners and the pipeline. Add the plugin for your dataframe
library (plugins live in `plugins/` of the same repo):

```sh
uv pip install "dataclean @ git+https://github.com/chetansinghsajwan/dataclean"
uv pip install "dataclean-pandas @ git+https://github.com/chetansinghsajwan/dataclean#subdirectory=plugins/dataclean-pandas"
```

With plain `pip`, drop `uv`. In a `uv` project, add them as dependencies:

```sh
uv add "dataclean @ git+https://github.com/chetansinghsajwan/dataclean"
uv add "dataclean-pandas @ git+https://github.com/chetansinghsajwan/dataclean#subdirectory=plugins/dataclean-pandas"
```

For PySpark and Unity Catalog, use `plugins/dataclean-databricks` instead.
Add `@<tag-or-commit>` after the repo URL to pin a version.

## Quickstart

```python
import pandas as pd
import dataclean

df = pd.DataFrame({
    "full_name": ["  john   SMITH ", "MARIA garcia-lopez"],
    "email": [" John.Smith@Example.COM ", "maria@example.com"],
    "phone": ["98765 43210", "+44 121 234 5678"],
    "country": ["india", "U.K."],
    "active": ["Yes", "no"],
})

result = dataclean.clean(df, keep_original=True)
cleaned = result.df  # the pandas DataFrame inside the wrapper
```

`clean()` returns the engine's `DataFrame` wrapper, and `.df` is your own
dataframe type. Plugins are loaded for you.

Detection uses the column name as well as the values, so use descriptive names
such as `email` or `phone`. `clean_paths()` and the CLI rename columns to
snake case first; `clean()` does not.

## Before and after

Output of the quickstart above. `keep_original=True` keeps the raw values of
every cleaned column as `<column>_uncleaned`.

| Column | Before | After |
| --- | --- | --- |
| `full_name` | `john   SMITH` | `john SMITH` |
| `email` | ` John.Smith@Example.COM ` | `john.smith@example.com` |
| `phone` | `98765 43210` | `+919876543210` |
| `phone` | `+44 121 234 5678` | `+441212345678` |
| `country` | `india` | `India` |
| `country` | `U.K.` | `United Kingdom` |
| `active` | `Yes` / `no` | `True` / `False` |

## Choosing cleaners

```python
dataclean.clean(
    df,
    column_cleaners={"contact": "EmailCleaner"},  # force a cleaner for a column
    ignore_cols=["notes"],  # leave a column alone
)
```

A cleaner is given by its registered name or as an instance. `EnumCleaner`
needs `cases=`, so it is never auto-detected. See
[Built-in Cleaners](docs/cleaners.md) for every cleaner and its options.

## Cleaning tables and files at rest

`clean_paths()` and the CLI find datasets with a glob or a regex, clean each
one, and write it to a path built from a template.

```sh
dataclean clean "data/raw/*.csv" "data/clean/*.csv" --catalog pandas
dataclean clean "re:data/report_\d+\.csv" "out/*.csv" --keep-original
dataclean clean "data/raw/*.csv" "out/*.csv" --col contact=EmailCleaner --ignore-col notes
```

```python
dataclean.clean_paths(["data/raw/*.csv"], write_path="data/clean/*.csv")
```

Paths take a scheme prefix that picks the catalog: `path:` or `pandas:` for
local files (no prefix also means local), `ibis:` for ibis, and `databricks:`
for Unity Catalog tables. Use `--dry-run` to see what a run would touch without
reading or writing anything.

## Databricks

Install `dataclean-databricks` and name tables as `catalog.schema.table`.
Each part takes `*` and `?`, a missing part means `*`, and `re:<regex>` matches
the full table name.

```python
dataclean.clean_paths(
    ["databricks:prod.raw.cust_*"],
    write_path="databricks:prod.clean.cust_*",
)
```

- **Cluster:** `dataclean` must be installed on the cluster. Setting
  `DATACLEAN_DATABRICKS_UPLOAD_LOCAL` uploads local packages instead.
- **Writes:** writing fails if the target table already exists.
- **Speed:** column detection makes many round trips to the cluster, so a wide
  table takes minutes to start.

## dbt

Not built yet. The plan for v1 is a dbt Python model that calls `clean()` on
the Databricks dataframe. SQL macros are future work. See
[the release plan](docs/release-plan.md).

## Develop

The repo uses Devbox, `uv` and Taskfile:

```sh
task setup   # install everything
task check   # format check, lint and type check
task test    # run the tests
```

Full docs: [Getting Started](docs/getting-started.md),
[Concepts](docs/concepts.md), [Configuration](docs/configuration.md),
[Writing your own cleaner](docs/custom-cleaners.md) and
[Plugins](docs/plugins.md).
