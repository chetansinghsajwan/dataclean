# dataclean

`dataclean` is an engine-agnostic, column-cleaning pipeline for tabular data.
You give it a dataframe (pandas, PySpark, or anything else an installed
engine adapter supports) and a set of `Cleaner`s, and it figures out which
cleaner applies to which column — either because you told it explicitly, or
because it auto-detected a match — and writes the cleaned values back.

```python
import dataclean

cleaned_df = dataclean.clean(df)
```

That's the whole quick-start. `clean()` auto-loads any installed `dataclean-*`
plugin, resolves a `Cleaner` for every column it recognizes (emails, phone
numbers, country names, UUIDs, dates, and more — see
[Built-in Cleaners](cleaners.md)), and returns the cleaned result.

!!! note "You need an engine plugin"
    The core `dataclean` package ships zero `DataFrame` engine adapters and
    zero `Catalog` implementations — only the cleaners themselves. For
    `dataclean.clean(df)` to actually run against a real pandas/PySpark
    object, an engine plugin such as `dataclean-pandas` or
    `dataclean-databricks` must be installed alongside it. See
    [Getting Started](getting-started.md).

## Where to go next

- **[Getting Started](getting-started.md)** — install `dataclean` plus an
  engine plugin, and run your first `clean()` call.
- **[Concepts](concepts.md)** — how `Pipeline.fit_transform` actually
  resolves cleaners to columns, what auto-detection means mechanically, and
  what the dependency-resolution errors mean when your columns are
  ambiguous.
- **[Built-in Cleaners](cleaners.md)** — every cleaner that ships with
  `dataclean` today: what it expects, what it produces, and known gotchas.
- **[Writing a Custom Cleaner](custom-cleaners.md)** — subclass `Cleaner` to
  handle a data shape none of the built-ins cover.
- **[Engines, Catalogs & Plugins](plugins.md)** — write a new `DataFrame`
  engine adapter or `Catalog`, and how the `dataclean-*` plugin discovery
  mechanism works.
- **[Configuration](configuration.md)** — the global `Config` singleton,
  `ColRenamer`, and the difference between `clean()` and `clean_paths()`.
- **[Roadmap](rust-migrate-plan.md)** — a forward-looking design proposal for
  a future Rust-backed core. Not implemented yet; the rest of these docs
  describe the current, shipped Python implementation.

## API Reference

Every public class and function is also documented from its docstrings in
the auto-generated API reference, linked in the site navigation.
