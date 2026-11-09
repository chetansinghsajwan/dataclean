# First Release Plan

Status: Draft. Public release on PyPI.

This plan covers what must be done before the first public release of
`dataclean` and its plugins. Items are ordered by dependency.

## Work items

| Order | Item | Depends on | Size |
| --- | --- | --- | --- |
| 1 | Collect sample datasets (done) | none | S |
| 2 | Cleaner audit: implement and auto-detect | 1 | L |
| 3 | Override automatic cleaner allocation (done) | none | S |
| 4 | Retain original values (done) | none | M |
| 5 | List datasets by regex (done) | none | M |
| 6 | Databricks support (in progress) | 2, 5 | L |
| 7 | dbt usage (approach only) | 6 | S |
| 8 | README | 3, 4, 5, 7 | S |
| 9 | Agent skill | 8 | S |

## Details

### 1. Sample datasets

Status: done. The datasets in `tests/fixtures/` are accepted as safe to
publish. The two contact files and the case list were reviewed value by value.

- Pick 5 to 8 messy datasets that together exercise every cleaner, including
  Indian data such as phone numbers, PIN codes, GSTIN and names.
- Keep them small and licensed for redistribution, since the repo is public.
  Prefer synthetic or properly anonymized data.
- Store them in `tests/fixtures/`, each with a hand-written expected-output
  file. They are the acceptance tests for items 2, 4 and 6.

### 2. Cleaner audit

Status: nearly done. 13 cleaners are registered and audited, and the
`match_score` audit is closed. The shared null-token helper is in
`dataclean.utils`; `NameCleaner` can adopt it, and `AddressCleaner` writes only
the outputs whose input role has a column.

- Run every cleaner against the datasets and list the gaps: missing cleaners
  and weak `match_score` implementations.
- Fix the gaps so each cleaner is both correct and auto-detecting.
- `EnumCleaner` needs `cases=`, so it is explicit-only for v1. Auto-detecting
  low-cardinality columns is in `docs/todo.md`.
- A column gets one output layout: `DateTimeCleaner` picks it per column
  through the new `Cleaner.fit` hook, and UK postcodes use one spacing.
- The sample fixtures are inputs only. They have no expected-output files.

### 3. Override automatic allocation

Status: done. `column_cleaners` is available on `clean` and `clean_paths`, and
the CLI has a repeatable `--col COLUMN=CLEANER`.

- A cleaner is given by registered name or as an instance. An unknown name
  raises `ValueError`. A column a dataset lacks is skipped.
- The per-column skip already existed as `ignore_cols` and `--ignore-col`, so
  no new option was added. `clean` now takes `ignore_cols` as well, and it wins
  over `column_cleaners`.

### 4. Retain original values

Status: done. `keep_original=True` with `original_suffix` (default
`_uncleaned`) is available on `Pipeline`, `clean`, `clean_paths` and the CLI.

- Only columns that a cleaner overwrites in place are copied, before any
  cleaner runs. Multi-output cleaners add new columns, so their input is kept.
- The copy uses a new `DataFrame.copy_cols`, because an identity `write_cols`
  passes values through text and would change non-string columns.
- A name collision raises `PipelineConfigError`.

### 5. List datasets by regex

Status: done, and checked against a real Unity workspace (Spark 4.1.0).

- A `re:<regex>` prefix selects a regex that must match the whole path, next
  to globs, in `Catalog.expand_paths`.
- Local catalogs (pandas, ibis) now expand globs and regexes against the file
  system through the shared `dataclean.utils.expand_local_paths`. Before, they
  returned the patterns unchanged.
- Unity Catalog filters `information_schema` with bound query parameters
  (`LIKE` for globs, `RLIKE` for regexes), which removes the SQL string
  interpolation. It is tested with a fake Spark session, and was also run
  read-only against a real workspace, covering literals, globs, regexes, a
  quote in a pattern, and several patterns in one query.

### 6. Databricks support

Status: in progress. The plugin now runs end to end on a real workspace and
matches the pandas results on every column of the contact fixture. Checked in
a scratch schema, with fake-Spark tests as the default tests.

Done:

- Workspace tests skip without `DATABRICKS_HOST` and `DATABRICKS_TOKEN`, so the
  plugin test run no longer hangs.
- Uploading local packages to the workspace is opt-in
  (`DATACLEAN_DATABRICKS_UPLOAD_LOCAL`). Without it, `dataclean` must be
  installed on the cluster. The cluster currently holds an old `dataclean`
  0.1.0 as a library, and changing it needs a token with the `libraries` scope.
- The Spark `read_cols` runs its callbacks on the driver. Before, columns
  detected only from their values, such as numbers, were never cleaned on
  Spark. A new contract test covers this.
- `NumericCleaner` outputs `DOUBLE`, since 32-bit floats lost digits on Spark
  and ibis.
- A new `DataType.LONG` (64-bit) is what `NumericCleaner` outputs for integers,
  since Spark `INT` is 32-bit. Other cleaners keep `INT`.

Left:

- Speed: a run takes minutes for 40 rows by 37 columns, almost all in
  detection. `BoolCleaner` and `GenderCleaner` scan every column, and each
  dataframe step is a round trip to the cluster. Fetch the schema lazily and
  share the scans between the enum cleaners, then measure again. The UDFs
  themselves are cheap.
- `UnityCatalog.write_df` fails on an existing table. Deliberately left as
  is, since a shared write mode would change `Catalog.write_df` for every
  plugin.
- Packaging: the placeholder description and the missing README.

### 7. dbt usage

Status: approach only. This is the plan, not an implementation.

- Option A: a dbt Python model that calls dataclean on Databricks. Quick, but
  specific to dbt Python models.
- Option B: SQL macros. Needs native expressions in the cleaner contract, so
  it is a larger redesign.
- Proposed for v1: option A, with option B documented as future work. Neither
  is built yet.

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
- **Public repo hygiene:** no secrets or internal data are in the history, and the release workflow
  publishes to PyPI.

## Open questions

- Release scope: core plus pandas and databricks only, with ibis and cch-crm
  deferred?
- dbt: is the Python-model route acceptable for v1?
