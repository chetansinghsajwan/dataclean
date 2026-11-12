"""Tests the Ibis catalog: file reads and writes, extension handling and path expansion."""

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
    """A fresh Ibis catalog backed by an in-memory DuckDB connection."""
    return IbisCatalog.instantiate()


def _source() -> IbisDataFrame:
    """A small two-column Ibis frame used as the data to write."""
    return IbisDataFrame(df=ibis.memtable(pd.DataFrame(DATA)))


def _roundtrip(catalog: IbisCatalog, path: Path) -> pd.DataFrame:
    """Writes the sample frame to a path and reads it back, sorted so row order does not matter."""
    catalog.write_df(_source(), str(path))
    result = catalog.read_df(str(path))
    assert isinstance(result, IbisDataFrame)
    return result.df.to_pandas().sort_values("n").reset_index(drop=True)


def test_schemes() -> None:
    """The ibis catalog answers only to the ibis scheme. If it claimed others it would
    grab paths that belong to some other catalog.
    """
    assert IbisCatalog.schemes == ("ibis",)


def test_instantiate_returns_catalog_with_duckdb_connection() -> None:
    """Asking the class for an instance gives a ready catalog that already holds a live
    DuckDB connection, so it can be used straight away.
    """
    catalog = IbisCatalog.instantiate()
    assert isinstance(catalog, IbisCatalog)
    assert catalog.con is not None


def test_expand_paths_echoes_paths(catalog: IbisCatalog) -> None:
    """Plain file names are handed back as they are, and naming a file twice only
    counts once. There is nothing to look up for them.
    """
    assert catalog.expand_paths(["a.csv", "b.csv", "a.csv"]) == {"a.csv", "b.csv"}


def test_csv_roundtrip(catalog: IbisCatalog, tmp_path: Path) -> None:
    """We write a small frame to CSV and read it back. The names and numbers should
    come out the same, so nothing gets lost on the way.
    """
    df = _roundtrip(catalog, tmp_path / "x.csv")
    assert list(df["name"]) == ["a", "b"]
    assert list(df["n"]) == [1, 2]


def test_parquet_roundtrip(catalog: IbisCatalog, tmp_path: Path) -> None:
    """Same round trip as CSV, this time through Parquet. The names and numbers should
    come back unchanged.
    """
    df = _roundtrip(catalog, tmp_path / "x.parquet")
    assert list(df["name"]) == ["a", "b"]
    assert list(df["n"]) == [1, 2]


def test_read_unsupported_extension_raises(
    catalog: IbisCatalog, tmp_path: Path
) -> None:
    """Reading an xlsx file is not something this catalog does, and it should say so
    with a clear error. Quietly guessing a format would only cause confusing
    failures later.
    """
    with pytest.raises(ValueError, match="Unsupported file extension"):
        catalog.read_df(str(tmp_path / "x.xlsx"))


def test_write_unsupported_extension_raises(
    catalog: IbisCatalog, tmp_path: Path
) -> None:
    """Writing to an xlsx path is not supported either, and should fail with the same
    clear error rather than guess.
    """
    with pytest.raises(ValueError, match="Unsupported file extension"):
        catalog.write_df(_source(), str(tmp_path / "x.xlsx"))


def test_read_no_extension_raises(catalog: IbisCatalog, tmp_path: Path) -> None:
    """A path with no extension gives us no clue what kind of file it is. Reading it
    should fail with the same clear error.
    """
    with pytest.raises(ValueError, match="Unsupported file extension"):
        catalog.read_df(str(tmp_path / "noext"))


def test_write_wrong_dataframe_type_raises(
    catalog: IbisCatalog, tmp_path: Path
) -> None:
    """Handing a pandas frame to the Ibis catalog's writer should be refused. A loud
    error is better than quietly mishandling a frame it does not understand.
    """
    pandas_df = PandasDataFrame(pd.DataFrame(DATA))
    with pytest.raises((AssertionError, TypeError)):
        catalog.write_df(pandas_df, str(tmp_path / "x.csv"))


def test_dotted_csv_name(catalog: IbisCatalog, tmp_path: Path) -> None:
    """A name like report.2024.csv has extra dots in it. Its extension is still csv, so
    it should round trip without trouble.
    """
    _roundtrip(catalog, tmp_path / "report.2024.csv")


def test_dotted_parquet_name(catalog: IbisCatalog, tmp_path: Path) -> None:
    """A name like data.v1.parquet has an extra dot too. The extension is still
    parquet, so it should round trip fine.
    """
    _roundtrip(catalog, tmp_path / "data.v1.parquet")


def test_uppercase_extension(catalog: IbisCatalog, tmp_path: Path) -> None:
    """A file called X.CSV still counts as CSV. Exports from other systems often shout
    their extensions.
    """
    _roundtrip(catalog, tmp_path / "X.CSV")


def test_expand_paths_expands_globs_and_regexes(
    catalog: IbisCatalog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In a folder with two CSVs and a text file, a star glob and a re: pattern both
    pick out the two CSVs. That is how a user names many files in one go.
    """
    for name in ("a.csv", "b.csv", "c.txt"):
        (tmp_path / name).write_text("x")
    monkeypatch.chdir(tmp_path)

    assert catalog.expand_paths(["*.csv"]) == {"a.csv", "b.csv"}
    assert catalog.expand_paths([r"re:[ab]\.csv"]) == {"a.csv", "b.csv"}
