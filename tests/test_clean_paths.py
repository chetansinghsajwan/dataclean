from collections.abc import Iterable

import pandas as pd
import pytest
from dataclean_pandas import PandasDataFrame

from dataclean import (
    Catalog,
    CleanPathResult,
    ColRenamer,
    DataFrame,
    clean_paths,
    config,
)


class DryRunCatalog(Catalog):
    def __init__(self) -> None:
        self.expanded_paths: list[str] = []

    def expand_paths(self, paths: Iterable[str]) -> set[str]:
        self.expanded_paths = list(paths)
        return {"dev.integration.clients"}

    def read_df(self, path: str) -> DataFrame:
        raise AssertionError("dry runs must not read dataframes")

    def write_df(self, df: DataFrame, path: str) -> None:
        raise AssertionError("dry runs must not write dataframes")


def test_clean_paths_dry_run_stops_before_reading_dataframes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    catalog = DryRunCatalog()

    result = clean_paths(
        paths=["dev.integration.*"],
        write_path="dev_chetan_signh.*",
        catalog=catalog,
        dry_run=True,
    )

    assert catalog.expanded_paths == ["dev.integration.*"]
    assert isinstance(result, CleanPathResult)


class InMemoryCatalog(Catalog):
    """An in-memory catalog backed by a dict of pandas DataFrames, for
    exercising `clean_paths`' cleaning/renaming logic without touching disk.
    """

    def __init__(self, dfs: dict[str, pd.DataFrame]) -> None:
        self._dfs = dfs
        self.written: dict[str, DataFrame] = {}

    def expand_paths(self, paths: Iterable[str]) -> set[str]:
        return set(paths)

    def read_df(self, path: str) -> DataFrame:
        return PandasDataFrame(self._dfs[path].copy())

    def write_df(self, df: DataFrame, path: str) -> None:
        self.written[path] = df


def test_clean_paths_ignore_cols_are_not_cleaned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    catalog = InMemoryCatalog({"in.csv": pd.DataFrame({"country": ["IN"]})})

    clean_paths(
        paths=["in.csv"],
        write_path="out.csv",
        catalog=catalog,
        rename_cols=False,
        ignore_cols=["country"],
    )

    written = catalog.written["out.csv"]
    assert written.df is not None
    assert written.df["country"].iloc[0] == "IN"


def test_clean_paths_cleaners_restricts_to_named_cleaners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    catalog = InMemoryCatalog({"in.csv": pd.DataFrame({"country": ["IN"]})})

    clean_paths(
        paths=["in.csv"],
        write_path="out.csv",
        catalog=catalog,
        rename_cols=False,
        cleaners=["EmailCleaner"],
    )

    # CountryCleaner was excluded, so the country column is left untouched.
    written = catalog.written["out.csv"]
    assert written.df is not None
    assert written.df["country"].iloc[0] == "IN"


def test_clean_paths_unknown_cleaner_name_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    catalog = InMemoryCatalog({"in.csv": pd.DataFrame({"country": ["IN"]})})

    with pytest.raises(ValueError, match="Unknown cleaner"):
        clean_paths(
            paths=["in.csv"],
            write_path="out.csv",
            catalog=catalog,
            cleaners=["NotARealCleaner"],
        )


def test_clean_paths_clean_cols_false_skips_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    catalog = InMemoryCatalog({"in.csv": pd.DataFrame({"Client Country": ["IN"]})})

    clean_paths(
        paths=["in.csv"],
        write_path="out.csv",
        catalog=catalog,
        clean_cols=False,
    )

    written = catalog.written["out.csv"]
    assert written.df is not None
    # Columns are still auto-renamed, but values are left uncleaned.
    assert list(written.df.columns) == ["client_country"]
    assert written.df["client_country"].iloc[0] == "IN"


def test_clean_paths_rename_col_map_applies_even_without_auto_rename(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    catalog = InMemoryCatalog({"in.csv": pd.DataFrame({"Client Country": ["IN"]})})

    clean_paths(
        paths=["in.csv"],
        write_path="out.csv",
        catalog=catalog,
        clean_cols=False,
        rename_cols=False,
        rename_col_map={"Client Country": "country_code"},
    )

    written = catalog.written["out.csv"]
    assert written.df is not None
    assert list(written.df.columns) == ["country_code"]


def test_clean_paths_col_renamer_overrides_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    catalog = InMemoryCatalog({"in.csv": pd.DataFrame({"Client Country": ["IN"]})})

    clean_paths(
        paths=["in.csv"],
        write_path="out.csv",
        catalog=catalog,
        clean_cols=False,
        col_renamer=ColRenamer(case="upper_snake"),
    )

    written = catalog.written["out.csv"]
    assert written.df is not None
    assert list(written.df.columns) == ["CLIENT_COUNTRY"]


def test_clean_paths_no_write_path_does_not_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    catalog = InMemoryCatalog({"in.csv": pd.DataFrame({"country": ["IN"]})})

    result = clean_paths(
        paths=["in.csv"],
        write_path=None,
        catalog=catalog,
        clean_cols=False,
    )

    assert catalog.written == {}
    assert isinstance(result, CleanPathResult)


class NamedCatalog(Catalog):
    """Registered under `config.catalog_types` to test catalog resolution by name."""

    instances: list["NamedCatalog"] = []

    def __init__(self) -> None:
        NamedCatalog.instances.append(self)

    @classmethod
    def instantiate(cls) -> "NamedCatalog":
        return cls()

    def expand_paths(self, paths: Iterable[str]) -> set[str]:
        return set()

    def read_df(self, path: str) -> DataFrame:
        raise AssertionError

    def write_df(self, df: DataFrame, path: str) -> None:
        raise AssertionError


def test_clean_paths_resolves_catalog_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    monkeypatch.setattr(config, "catalog_types", [NamedCatalog])
    NamedCatalog.instances = []

    clean_paths(paths=[], catalog="named")

    assert len(NamedCatalog.instances) == 1


def test_clean_paths_unknown_catalog_name_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    monkeypatch.setattr(config, "catalog_types", [NamedCatalog])

    with pytest.raises(ValueError, match="No registered catalog type matches"):
        clean_paths(paths=[], catalog="nope")


class SchemeCatalog(Catalog):
    """Records what it is asked to read/write, to test scheme routing."""

    schemes = ("mem",)

    def __init__(self) -> None:
        self.read: list[str] = []
        self.written: dict[str, DataFrame] = {}

    @classmethod
    def instantiate(cls) -> "SchemeCatalog":
        return cls()

    def expand_paths(self, paths: Iterable[str]) -> set[str]:
        return set(paths)

    def read_df(self, path: str) -> DataFrame:
        self.read.append(path)
        return PandasDataFrame(pd.DataFrame({"country": ["IN"]}))

    def write_df(self, df: DataFrame, path: str) -> None:
        self.written[path] = df


class DefaultCatalog(SchemeCatalog):
    schemes = ("",)


def test_clean_paths_routes_by_scheme_and_strips_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    monkeypatch.setattr(config, "catalog_types", [SchemeCatalog, DefaultCatalog])
    seen: list[SchemeCatalog] = []
    original = SchemeCatalog.instantiate.__func__  # type: ignore[attr-defined]

    def tracking(cls: type[SchemeCatalog]) -> SchemeCatalog:
        instance = original(cls)
        seen.append(instance)
        return instance

    monkeypatch.setattr(SchemeCatalog, "instantiate", classmethod(tracking))

    clean_paths(
        paths=["mem:a", "b"],
        write_path="mem:out",
        rename_cols=False,
        clean_cols=False,
    )

    by_type = {type(c): c for c in seen}
    assert by_type[SchemeCatalog].read == ["a"]
    assert by_type[DefaultCatalog].read == ["b"]
    assert set(by_type[SchemeCatalog].written) == {"out"}


def test_clean_paths_unknown_scheme_raises_with_windows_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    monkeypatch.setattr(config, "catalog_types", [DefaultCatalog])

    with pytest.raises(ValueError, match="path:C:/data"):
        clean_paths(paths=["C:/data/x.csv"])


def test_register_catalog_rejects_duplicate_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "catalog_types", [SchemeCatalog])

    class Other(SchemeCatalog):
        pass

    with pytest.raises(ValueError, match="already registered"):
        config.register_catalog(Other)


def test_clean_paths_uses_global_catalog_when_none_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    monkeypatch.setattr(config, "catalog_types", [])
    catalog = InMemoryCatalog({"in.csv": pd.DataFrame({"a": ["x"]})})
    monkeypatch.setattr(config, "catalog", catalog)

    clean_paths(paths=["in.csv"], write_path="out.csv", clean_cols=False)

    assert set(catalog.written) == {"out.csv"}


def test_clean_paths_ignores_global_catalog_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    monkeypatch.setattr(config, "catalog_types", [])
    monkeypatch.setattr(
        config, "catalog", InMemoryCatalog({"in.csv": pd.DataFrame({"a": ["x"]})})
    )

    with pytest.raises(ValueError, match="No catalog registered"):
        clean_paths(paths=["in.csv"], use_global_config=False)


def test_clean_paths_explicit_catalog_does_not_parse_prefixes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    catalog = InMemoryCatalog({"C:/in.csv": pd.DataFrame({"a": ["x"]})})

    clean_paths(
        paths=["C:/in.csv"], write_path="D:/out.csv", catalog=catalog, clean_cols=False
    )

    assert set(catalog.written) == {"D:/out.csv"}


def test_clean_paths_can_write_to_a_different_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    source, dest = SchemeCatalog(), DefaultCatalog()
    monkeypatch.setattr(SchemeCatalog, "instantiate", classmethod(lambda cls: source))
    monkeypatch.setattr(DefaultCatalog, "instantiate", classmethod(lambda cls: dest))
    monkeypatch.setattr(config, "catalog_types", [SchemeCatalog, DefaultCatalog])

    clean_paths(paths=["mem:a"], write_path="out", rename_cols=False, clean_cols=False)

    assert source.read == ["a"]
    assert source.written == {}
    assert set(dest.written) == {"out"}


def test_clean_paths_expands_each_catalog_once_with_its_own_patterns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    first, second = SchemeCatalog(), DefaultCatalog()
    monkeypatch.setattr(SchemeCatalog, "instantiate", classmethod(lambda cls: first))
    monkeypatch.setattr(DefaultCatalog, "instantiate", classmethod(lambda cls: second))
    monkeypatch.setattr(config, "catalog_types", [SchemeCatalog, DefaultCatalog])

    clean_paths(
        paths=["mem:a", "x", "mem:b", "y"],
        rename_cols=False,
        clean_cols=False,
    )

    assert sorted(first.read) == ["a", "b"]
    assert sorted(second.read) == ["x", "y"]


def test_clean_paths_catalog_that_cannot_instantiate_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Unavailable(SchemeCatalog):
        schemes = ("na",)

        @classmethod
        def instantiate(cls) -> None:  # type: ignore[override]
            return None

    monkeypatch.setattr(config, "auto_load_plugins", False)
    monkeypatch.setattr(config, "catalog_types", [Unavailable])

    with pytest.raises(ValueError, match="could not be instantiated"):
        clean_paths(paths=["na:a"])


def test_clean_paths_logs_expanded_and_mapped_paths(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    catalog = InMemoryCatalog({"in.csv": pd.DataFrame({"a": ["x"]})})

    with caplog.at_level("DEBUG", logger="dataclean.clean"):
        clean_paths(
            paths=["in.csv"],
            write_path="out.csv",
            catalog=catalog,
            clean_cols=False,
        )

    assert "in.csv -> out.csv" in caplog.text
