# First Release Plan

Status: Draft. Public release on PyPI.

This plan covers what must be done before the first public release of
`dataclean` and its plugins. Items are ordered by dependency.

## Work items

| Order | Item | Depends on | Size |
| --- | --- | --- | --- |
| 1 | Collect sample datasets | none | S |
| 2 | Cleaner audit: implement and auto-detect | 1 | L |
| 3 | Override automatic cleaner allocation | none | S |
| 4 | Retain original values | none | M |
| 5 | List datasets by regex | none | M |
| 6 | Databricks support | 2, 5 | L |
| 7 | dbt usage | 6 | M to L |
| 8 | README | 3, 4, 5, 7 | S |
| 9 | Agent skill | 8 | S |

## Details

### 1. Sample datasets

- Pick 5 to 8 messy datasets that together exercise every cleaner, including
  Indian data such as phone numbers, PIN codes, GSTIN and names.
- Keep them small and licensed for redistribution, since the repo is public.
  Prefer synthetic or properly anonymized data.
- Store them in `tests/fixtures/`, each with a hand-written expected-output
  file. They are the acceptance tests for items 2, 4 and 6.

### 2. Cleaner audit

- Run every cleaner against the datasets and list the gaps: missing cleaners
  and weak `match_score` implementations.
- Fix the gaps so each cleaner is both correct and auto-detecting.
- `EnumCleaner` needs `cases=`, so it cannot auto-detect without
  configuration. Decide whether it is explicit-only.
- Not yet checked: which built-in cleaners lack `match_score`.

### 3. Override automatic allocation

- `Pipeline` already accepts `column_cleaners`.
- Expose it in `clean_paths` and the CLI, for example
  `--col email=EmailCleaner`.
- Add a per-column skip, beyond the existing `ignore_cols`.

### 4. Retain original values

- Add `keep_original=True` with a column suffix such as `_raw`, so cleaned and
  uncleaned data can be compared side by side.
- Implement it by copying the column before cleaning, using `write_cols` with
  an identity function, so the `DataFrame` interface does not change.
- Decide how name collisions are handled.

### 5. List datasets by regex

- Support regex alongside globs in `Catalog.expand_paths`, for example with an
  `re:` pattern prefix.
- Local catalogs match against the directory listing.
- Unity Catalog filters `information_schema` with parameterized queries. This
  also removes the SQL string interpolation in `UnityCatalog._expand_paths`.

### 6. Databricks support

- The databricks plugin tests currently error at setup, so there is no
  working baseline yet.
- End-to-end runs need a Unity workspace or a Databricks Connect profile.
- Measure Python UDF cost on Spark with the sample datasets. It is the main
  performance risk.

### 7. dbt usage

- Option A: a dbt Python model that calls dataclean on Databricks. Quick, but
  specific to dbt Python models.
- Option B: SQL macros. Needs native expressions in the cleaner contract, so
  it is a larger redesign.
- Proposed for v1: option A, with option B documented as future work.

### 8. README

- Install, a 10-line quickstart, and a before/after table from a sample
  dataset.
- Databricks and dbt usage, and scheme-prefixed paths (`path:`, `databricks:`).

### 9. Agent skill

- A `SKILL.md` covering when to use dataclean, the `clean` and `clean_paths`
  calls, and overriding cleaners.
- Written last so it describes the final API.

## Release gates

- **Quality:** `task check` is green, `mypy --strict` has been run clean, and
  there are no xfailed tests.
- **Packaging:** the plugins have complete `pyproject.toml` metadata
  (dependency on `dataclean`, description, README). The `dataclean-ibis`
  plugin is currently missing these.
- **Versioning:** decide plugin versioning and the publish order for
  `dataclean` and its plugins.
- **Docs:** the docs match the scheme-prefix path routing and the new options.
- **Public repo hygiene:** dataset licenses are checked, no secrets or
  internal data are in the history, and the release workflow publishes to PyPI.

## Open questions

- Dataset sources: real data to anonymize, or synthetic?
- Release scope: core plus pandas and databricks only, with ibis and cch-crm
  deferred?
- dbt: is the Python-model route acceptable for v1?
