# Engines, Catalogs & Plugins

`dataclean` core ships the `Cleaner`/`Pipeline` machinery but **no concrete
`DataFrame` or `Catalog` implementation** — those come from separate
`dataclean-*` plugin packages, discovered and loaded automatically. This
page covers writing a `DataFrame` adapter, writing a `Catalog`, and how the
plugin distribution mechanism works, using this repo's own
`dataclean-pandas` package as the worked example throughout.

## Writing a `DataFrame` engine adapter

Subclass `DataFrame` (`src/dataclean/engine/dataframe.py`) and implement its
abstract methods against your dataframe library's native API:

- `supports(df) -> bool` (`staticmethod`) — type-detection predicate; this is
  what `Pipeline` uses to pick an adapter for a raw object.
- `cols() -> tuple[tuple[str, DataType], ...]`, `rename_cols`, `read_cols`,
  `write_cols`, `remove_cols`, `cast_cols` — column management. Most other
  methods mutate the wrapped dataframe in place; the query-style ones
  (`group_by`, `agg`, `distinct`, `select`, `strip`, `nullif`, `order_by`,
  `limit`, `filter_null`) return a **new** `DataFrame` to support chaining.
- `count`, `collect` — materialize rows.

`dataclean-pandas`'s `PandasDataFrame`
(`plugins/dataclean-pandas/src/dataclean_pandas/dataframe.py`) is a complete
real-world reference implementation to copy the shape of. See
[Concepts](concepts.md#the-dataframe-engine-abstraction) for the mutate vs.
returns-new-`DataFrame` convention, and the API reference for the full
abstract method list.

### Verifying it: the shared contract test suite

`dataclean.testing.BaseDataFrameTests` gives you 7 tests for free — column
management only (`supports`, `cols`, `rename_cols`, `write_cols`,
`read_cols`, `remove_cols`, `cast_cols`). Subclass it and override the
`wrapper` fixture:

```python
import pandas as pd
import pytest
from dataclean.testing import RAW_TEST_DATA, BaseDataFrameTests
from dataclean_pandas import PandasDataFrame


class TestPandasDataFrame(BaseDataFrameTests):
    @pytest.fixture
    def wrapper(self) -> PandasDataFrame:
        return PandasDataFrame(df=pd.DataFrame(RAW_TEST_DATA))
```

This is copied nearly verbatim from
`plugins/dataclean-pandas/tests/test_dataframe.py`.

!!! note "The shared suite does not cover every method"
    `group_by`, `agg`, `distinct`, `select`, `strip`, `nullif`, `order_by`,
    `limit`, `filter_null`, `count`, and `collect` are abstract on
    `DataFrame` but **not** exercised by `BaseDataFrameTests`. Write your own
    tests for those — `dataclean-pandas`'s test file adds exactly this set of
    engine-specific tests on top of the shared suite; use it as the pattern.

## Writing a `Catalog`

A `Catalog` (`src/dataclean/engine/catalog.py`) lets `clean_paths()` discover
and read/write data without knowing the storage backend:

- `expand_paths(paths) -> set[str]` — expand glob-style patterns into
  concrete paths (`@abstractmethod`).
- `read_df(path) -> DataFrame` / `write_df(df, path)` (`@abstractmethod`).
- `supports_env() -> bool` / `instantiate() -> Self | None` (classmethods,
  default `False`/`None`) — override these so `clean_paths()` can
  auto-detect and construct your catalog from the environment (e.g. an env
  var or an active session) when no catalog is passed explicitly.
- `priority: ClassVar[int]` — `CatalogPriority.GENERIC` (default) or
  `ENV_DEPENDENT`. `Config.register_catalog` keeps registered catalog
  *types* sorted by descending priority, so environment-specific catalogs
  are tried before generic fallbacks during auto-detection.

`dataclean-pandas`'s `PandasCatalog` is the reference example in this repo.

## The plugin distribution mechanism

`PluginLoader` (`src/dataclean/plugins/loader.py`) discovers plugins purely
by distribution-name prefix — **no `entry_points` group is used**:

1. **Distribution name** must start with `dataclean-` (e.g.
   `dataclean-pandas`), found via `importlib.metadata.distributions()`.
2. **Importable module name** is that name with hyphens replaced by
   underscores (`dataclean-pandas` → `dataclean_pandas`).
3. The module must expose a module-level `info` attribute that is *exactly*
   a `PluginInfo` instance — the check is `type(x) is PluginInfo`, not
   `isinstance`, so subclassing `PluginInfo` will fail registration with a
   `RuntimeError`.

`dataclean-pandas`'s `__init__.py` is the template every plugin follows:

```python
from dataclean import PluginInfo
from dataclean_pandas.catalog import PandasCatalog
from dataclean_pandas.dataframe import PandasDataFrame

info = PluginInfo(
    name="dataclean-pandas",
    catalog_types={PandasCatalog},
    dataframe_types={PandasDataFrame},
)
```

`PluginLoader.load_plugins()` — called automatically by `clean()`/
`clean_paths()` when `config.auto_load_plugins` is `True` (the default) —
finds every installed `dataclean-*` distribution and, for each one,
registers its `dataframe_types` via `config.register_dataframe`,
`catalog_types` via `config.register_catalog`, `presets` via
`config.register_preset`, and `cleaner_types` via `config.register_cleaner`.

!!! warning "Don't put custom cleaners in `PluginInfo.cleaner_types`"
    `PluginInfo.cleaner_types` is typed as `set[type[Cleaner]]` — *classes*,
    not instances — but `Config.register_cleaner` expects a `Cleaner`
    *instance* and is `@checked` (beartype-enforced). Passing a class through
    this path currently raises `BeartypeCallHintParamViolation` at plugin-load
    time. Until this is fixed upstream, register any custom cleaners a
    plugin wants to ship via `config.register_cleaner(MyCleaner())` in your
    own package's import-time code instead of via `PluginInfo.cleaner_types`.

## Preset (scaffolding only)

`Preset` (`src/dataclean/preset/__init__.py`) is an abstract class with
`match(ctx) -> float` and `get() -> dict[str, Cleaner]`, intended to let a
plugin bundle a ready-made cleaner assignment for a recognized schema shape.
It's registerable via `config.register_preset`/`PluginInfo.presets`, but
nothing in `clean()` or `clean_paths()` currently reads `config.presets` —
treat it as an extension point reserved for future use, not something that
changes cleaning behavior today.

## What's next

[Configuration](configuration.md) covers every `Config` field and the
`clean()`/`clean_paths()` split in full.
