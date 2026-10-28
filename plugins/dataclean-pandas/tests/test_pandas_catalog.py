from pathlib import Path

import pandas as pd
import pytest
from dataclean_pandas import PandasDataFrame
from dataclean_pandas.catalog import PandasCatalog

from dataclean import DataFrame

DATA = {"name": ["a", "b"], "n": [1, 2]}


def _write_source(path: Path) -> PandasDataFrame:
    return PandasDataFrame(pd.DataFrame(DATA))


def _roundtrip(path: Path) -> pd.DataFrame:
    catalog = PandasCatalog()
    catalog.write_df(_write_source(path), str(path))
    result = catalog.read_df(str(path))
    assert isinstance(result, PandasDataFrame)
    assert result.df is not None
    return result.df


def test_schemes_include_default_path_and_pandas() -> None:
    assert PandasCatalog.schemes == ("", "path", "pandas")


def test_instantiate_returns_catalog() -> None:
    assert isinstance(PandasCatalog.instantiate(), PandasCatalog)


def test_expand_paths_echoes_paths() -> None:
    assert PandasCatalog().expand_paths(["a.csv", "b.csv", "a.csv"]) == {
        "a.csv",
        "b.csv",
    }


def test_csv_roundtrip(tmp_path: Path) -> None:
    df = _roundtrip(tmp_path / "x.csv")
    assert list(df["name"]) == ["a", "b"]
    assert list(df["n"]) == [1, 2]


def test_parquet_roundtrip(tmp_path: Path) -> None:
    df = _roundtrip(tmp_path / "x.parquet")
    assert list(df["name"]) == ["a", "b"]
    assert list(df["n"]) == [1, 2]


def test_xlsx_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("openpyxl")
    df = _roundtrip(tmp_path / "x.xlsx")
    assert list(df["name"]) == ["a", "b"]


def test_read_unsupported_extension_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported file extension"):
        PandasCatalog().read_df(str(tmp_path / "x.txt"))


def test_write_unsupported_extension_raises(tmp_path: Path) -> None:
    df: DataFrame = _write_source(tmp_path)
    with pytest.raises(ValueError, match="Unsupported file extension"):
        PandasCatalog().write_df(df, str(tmp_path / "x.txt"))


def test_read_no_extension_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported file extension"):
        PandasCatalog().read_df(str(tmp_path / "noext"))


def test_dotted_csv_name(tmp_path: Path) -> None:
    _roundtrip(tmp_path / "report.2024.csv")


def test_dotted_parquet_name(tmp_path: Path) -> None:
    _roundtrip(tmp_path / "data.v1.parquet")


def test_uppercase_extension(tmp_path: Path) -> None:
    _roundtrip(tmp_path / "X.CSV")
