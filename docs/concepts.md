# Concepts

This page explains how the pieces fit together: the `Cleaner` contract, how
`Pipeline.fit_transform` turns a raw dataframe plus a list of cleaners into a
cleaned one, what "auto-detect" actually computes, and the abstractions
(`DataFrame`, `Catalog`, `checked`) everything else is built on.

## The `Cleaner` contract

Every cleaner is an immutable `@dataclass` subclass of `Cleaner`
(`src/dataclean/cleaners/cleaner.py`). The design goal, per the project's
`AGENTS.md`, is that all configuration and validation happens once, at
construction time — `__post_init__` resolves and caches `inputs`
(`InputSchema`) and `outputs` (`OutputSchema`) immediately, so there's no
repeated branching or validation cost per row during cleaning.

- **`InputSchema.Column`** describes one expected input: a `key` (the role
  name — `PRIMARY` = `"value"` for the common single-argument case),
  `required`, an optional `detector` (a sub-cleaner used just to score
  candidate columns for this role), and `name_hints` (candidate substrings
  used when matching a raw column name to this role).
- **`OutputSchema.Column`** describes one produced column: an optional
  `name` (`None` means "reuse the input column's name"), a `dtype`
  (`DataType`), and `roles` — semantic tags like `"country"` or `"postcode"`
  that other cleaners can depend on as *context inputs* (see
  [Dependency resolution](#dependency-resolution-and-its-errors) below).
- If you don't override `_inputs()`, the schema is **inferred from
  `clean_row`'s signature**: a single positional parameter becomes the
  `PRIMARY` role; multiple named parameters become named roles 1:1. This is
  why most simple cleaners never need to write an explicit `InputSchema` —
  see [Writing a Custom Cleaner](custom-cleaners.md).
- `match_score(df, cols) -> float` is how a cleaner tells the resolver how
  confident it is that it applies to a given column, on a `0.0`–`1.0` scale
  (`Cleaner.MIN_SCORE`/`MAX_SCORE`). The base implementation always returns
  `0.0` — every built-in cleaner that wants to participate in auto-detection
  overrides it. See [Auto-detection mechanics](#auto-detection-mechanics).

::: dataclean.cleaners.Cleaner

## How `Pipeline.fit_transform` works

`Pipeline` (`src/dataclean/pipeline/pipeline.py`) is constructed with a tuple
of `Cleaner`s (plus optional explicit `column_cleaners` and
`context_overrides`) and an `auto_detect` flag. Calling `fit_transform(df)`
does, in order:

1. **Wrap the raw dataframe.** If `df` isn't already a `DataFrame`, `Pipeline`
   iterates `config.dataframe_apis` and calls each registered adapter's
   `supports(df)`; the first match wraps it. If nothing matches, it raises
   `TypeError: Unsupported dataframe type`.
2. **Resolve column → cleaner assignments** via `Resolver.resolve` (see
   below) — every candidate `Assignment` (a cleaner, its matched input
   columns, and a confidence score) comes back, including auto-detected
   ones.
3. **Filter for `auto_detect=False`.** If the pipeline was built with
   `auto_detect=False`, only assignments with `confidence == 1.0` survive —
   i.e. only the columns you explicitly mapped via `column_cleaners`.
   Auto-matched assignments are dropped.
4. **Resolve dependencies and execution order** via `DependencyResolver` (see
   below) — this wires up any *context role* inputs (values a cleaner needs
   that come from another cleaner's output, not directly from a raw column)
   and topologically sorts all assignments into "waves": groups of
   assignments with no dependency on each other, ordered so producers run
   before consumers.
5. **Execute each wave.** For every assignment in a wave, `Pipeline` builds a
   `DataWriter` (read columns, a guarded call into `clean_row`, and the
   output column name(s)/dtype), then makes exactly **one** `df.write_cols(...)`
   call per wave — not one per cleaner.
6. Returns the (mutated in place) wrapped `DataFrame`.

A required input that is missing (`None`, or `NaN` for numeric engines) never
reaches `clean_row` at all — the pipeline short-circuits that row to `None`
output first. Cleaners don't need to guard against missing values themselves.

::: dataclean.pipeline.pipeline.Pipeline

## Auto-detection mechanics

"Auto-detect" is two cooperating pieces of resolution:

**Column ↔ cleaner assignment (`Resolver.resolve`,
`src/dataclean/pipeline/cleaner_resolver.py`).** Explicit `column_cleaners`
mappings always win first. Remaining cleaners are tried in order of *most
required input columns first* (so a multi-column cleaner like
`AddressCleaner` gets first pick over a permissive single-column one). A
single-input cleaner is scored against every still-unclaimed column and may
claim several at once (e.g. multiple `*_email` columns); a multi-input
cleaner greedily matches its best-scoring candidate for each role, and is
abandoned entirely if a **required** role can't find a candidate scoring
`>= 0.5`. That `0.5` threshold is the acceptance bar everywhere — columns no
cleaner scores highly enough for are simply left unassigned.

**Cleaner-level scoring (`match_score`)** follows one of a few patterns you
will see repeated across the built-ins (see [Built-in Cleaners](cleaners.md)
for exactly which cleaner uses which):

- **Column-name matching** — the cheapest and most common: check whether the
  column name contains/starts with/ends with certain substrings (e.g.
  `EmailCleaner` checking for `"email"`, `PhoneCleaner` checking for
  `phone`/`tel`/`mobile`/`fax`). These never look at the actual data.
- **Prefix/suffix/word matching with a value-sampling fallback**
  (`EnumCleaner`, inherited by `BoolCleaner` and `GenderCleaner`): if no
  configured name pattern matches, it samples up to the 100 most frequent
  distinct non-null values (`select → strip → nullif → filter_null →
  group_by → agg(count) → order_by(desc) → limit(100) → collect()`) and
  scores by the frequency-weighted fraction that match a configured case.
- **Weighted name + independent value-sampling** (`NumericCleaner`): 30% from
  name tokens, 70% from actually running `clean_row` against up to 100
  sampled raw values via `df.read_cols(...)` and measuring the success rate.

## Dependency resolution and its errors

Some cleaners need more than raw column values — they need a *role* another
cleaner produces (declared via that producer's `OutputSchema.Column.roles`).
`DependencyResolver` (`src/dataclean/pipeline/dependency_resolver.py`) wires
these edges and computes the wave ordering. When it can't, it raises one of
three exceptions (all subclasses of `PipelineConfigError` /
`DatacleanError`, so you can catch broadly at that level if you just need to
know "pipeline setup is broken"):

- **`MissingRequiredRoleError`** — a cleaner needs a required context role
  (e.g. `"country"`) but *nothing in this pipeline produces it at all*, or a
  `context_overrides` entry points at a column that isn't actually a
  producer of that role. **Fix:** add/enable a cleaner that produces the
  role, or correct/remove the override.
- **`AmbiguousRoleError`** — a required role has *multiple* candidate
  producers and the resolver can't tell which one belongs to which consumer.
  The classic case: `client_phone` and `manager_phone` both need a
  `"country"` role, and two columns both produce one, with no naming signal
  tying either country column to its matching phone column. **Fix:** rename
  columns so a consumer and its producer share a distinguishing token (e.g.
  `client_country` ↔ `client_phone`), or pass an explicit
  `context_overrides={"client_phone": {"country": "client_country"}}` to
  `Pipeline(...)`.
- **`CycleDetectedError`** — the producer/consumer graph has a cycle (cleaner
  A needs a role cleaner B produces, and B — directly or transitively —
  needs a role from A). **Fix:** this is a pipeline configuration problem,
  not something your data can fix — restructure which cleaner produces which
  role.

All three are raised inside `fit_transform()` at call time, not when the
`Pipeline` is constructed.

## The `DataFrame` engine abstraction

Per `AGENTS.md`: *"Never depend directly on the underlying implementation;
always manipulate data strictly using the `DataFrame` interface."* Every
cleaner, the `Pipeline`, and the resolvers only ever talk to a
`DataFrame` (`src/dataclean/engine/dataframe.py`) — an abstract, engine-agnostic
column API that concrete adapters (one per real dataframe library) implement.

Two conventions to know:

- Most methods (`rename_cols`, `write_cols`, `remove_cols`, `cast_cols`, ...)
  **mutate in place**. The query-style methods (`group_by`, `agg`,
  `distinct`, `select`, `strip`, `nullif`, `order_by`, `limit`,
  `filter_null`) return a **new** `DataFrame` to support chaining, mirroring
  the fluent chain `match_score` uses for value-sampling above.
- `DataReader` and `DataWriter` are the two declarative primitives the whole
  pipeline is built on: a `DataReader` invokes a callback per row for
  side effects only; a `DataWriter` computes and writes one or more output
  columns from one or more input columns. Every wave of `Pipeline.fit_transform`
  compiles down to exactly one `write_cols(writers)` call.

`dataclean` core ships **no concrete `DataFrame` implementation** — those
live in separate plugin packages (`dataclean-pandas`, `dataclean-databricks`
under this repo's `plugins/`). See [Engines, Catalogs & Plugins](plugins.md)
for how to write and test one, and the API reference for the full abstract
method list.

## The `Catalog` abstraction

A `Catalog` (`src/dataclean/engine/catalog.py`) is how `clean_paths()`
discovers, reads, and writes tables/files without knowing what storage
platform it's talking to: `expand_paths` (glob-style pattern expansion),
`read_df`/`write_df`, plus optional `supports_env()`/`instantiate()` hooks
for environment auto-detection. Registered catalog *types* are kept sorted
by descending `priority` (`CatalogPriority.GENERIC` vs. `ENV_DEPENDENT`), so
more environment-specific catalogs are tried before generic fallbacks.

Like `DataFrame`, `dataclean` core ships no concrete `Catalog` — real ones
come from plugins.

## The `checked` decorator

`checked` (`src/dataclean/types.py`) is a thin wrapper around
`beartype.beartype`, applied unconditionally. You'll see it on nearly every
dataclass in the codebase, always placed *above* `@dataclass` so it wraps the
generated `__init__`:

```python
@checked
@dataclass
class Foo: ...
```

This turns every declared type hint into an enforced runtime contract —
constructing a `DataWriter` with the wrong shape, or an `Assignment` with the
wrong type, fails immediately at the boundary instead of propagating bad
state silently through the pipeline. A related `dev_checked` variant only
applies the check when `APP_ENV=dev`, for a zero-overhead production path.

## What's next

- **[Built-in Cleaners](cleaners.md)** for the concrete `match_score`/
  `clean_row` behavior of every shipped cleaner.
- **[Writing a Custom Cleaner](custom-cleaners.md)** to apply everything on
  this page to your own `Cleaner` subclass.
- **[Engines, Catalogs & Plugins](plugins.md)** to implement `DataFrame`/
  `Catalog` for a new platform.
- **[Roadmap](rust-migrate-plan.md)** describes a possible future
  Rust-backed core. It is a design proposal only — nothing on this page is
  affected by it today.
