from pathlib import Path

import ibis
import pandas as pd
import pytest
from dataclean_ibis import IbisDataFrame
from dataclean_ibis.catalog import IbisCatalog
from dataclean_pandas import PandasDataFrame

DATA = {"name": ["a", "b"], "n": [1, 2]}


@pytest.fixture
def catalog() -> IbisCatalog:
    return IbisCatalog.instantiate()


def _source() -> IbisDataFrame:
    return IbisDataFrame(df=ibis.memtable(pd.DataFrame(DATA)))


def _roundtrip(catalog: IbisCatalog, path: Path) -> pd.DataFrame:
    catalog.write_df(_source(), str(path))
    result = catalog.read_df(str(path))
    assert isinstance(result, IbisDataFrame)
    return result.df.to_pandas().sort_values("n").reset_index(drop=True)


def test_schemes() -> None:
    assert IbisCatalog.schemes == ("ibis",)


def test_instantiate_returns_catalog_with_duckdb_connection() -> None:
    catalog = IbisCatalog.instantiate()
    assert isinstance(catalog, IbisCatalog)
    assert catalog.con is not None


def test_expand_paths_echoes_paths(catalog: IbisCatalog) -> None:
    assert catalog.expand_paths(["a.csv", "b.csv", "a.csv"]) == {"a.csv", "b.csv"}


def test_csv_roundtrip(catalog: IbisCatalog, tmp_path: Path) -> None:
    df = _roundtrip(catalog, tmp_path / "x.csv")
    assert list(df["name"]) == ["a", "b"]
    assert list(df["n"]) == [1, 2]


def test_parquet_roundtrip(catalog: IbisCatalog, tmp_path: Path) -> None:
    df = _roundtrip(catalog, tmp_path / "x.parquet")
    assert list(df["name"]) == ["a", "b"]
    assert list(df["n"]) == [1, 2]


def test_read_unsupported_extension_raises(
    catalog: IbisCatalog, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match="Unsupported file extension"):
        catalog.read_df(str(tmp_path / "x.xlsx"))


def test_write_unsupported_extension_raises(
    catalog: IbisCatalog, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match="Unsupported file extension"):
        catalog.write_df(_source(), str(tmp_path / "x.xlsx"))


def test_read_no_extension_raises(catalog: IbisCatalog, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported file extension"):
        catalog.read_df(str(tmp_path / "noext"))


def test_write_wrong_dataframe_type_raises(
    catalog: IbisCatalog, tmp_path: Path
) -> None:
    pandas_df = PandasDataFrame(pd.DataFrame(DATA))
    with pytest.raises((AssertionError, TypeError)):
        catalog.write_df(pandas_df, str(tmp_path / "x.csv"))


def test_dotted_csv_name(catalog: IbisCatalog, tmp_path: Path) -> None:
    _roundtrip(catalog, tmp_path / "report.2024.csv")


def test_dotted_parquet_name(catalog: IbisCatalog, tmp_path: Path) -> None:
    _roundtrip(catalog, tmp_path / "data.v1.parquet")


def test_uppercase_extension(catalog: IbisCatalog, tmp_path: Path) -> None:
    _roundtrip(catalog, tmp_path / "X.CSV")
