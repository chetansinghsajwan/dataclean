"""Tests the pandas catalog: file reads and writes, extension handling and path expansion."""

from pathlib import Path

import pandas as pd
import pytest
from dataclean_pandas import PandasDataFrame
from dataclean_pandas.catalog import PandasCatalog

from dataclean import DataFrame

DATA = {"name": ["a", "b"], "n": [1, 2]}


def _write_source(path: Path) -> PandasDataFrame:
    """A small two-column pandas frame used as the data to write."""
    return PandasDataFrame(pd.DataFrame(DATA))


def _roundtrip(path: Path) -> pd.DataFrame:
    """Writes the sample frame to a path and reads it back through the catalog."""
    catalog = PandasCatalog()
    catalog.write_df(_write_source(path), str(path))
    result = catalog.read_df(str(path))
    assert isinstance(result, PandasDataFrame)
    assert result.df is not None
    return result.df


def test_schemes_include_default_path_and_pandas() -> None:
    """The pandas catalog is the default, so plain paths, path: and pandas: all land
    here. Someone who types just a file name should get this catalog.
    """
    assert PandasCatalog.schemes == ("", "path", "pandas")


def test_instantiate_returns_catalog() -> None:
    """Asking the class for an instance should give a working pandas catalog."""
    assert isinstance(PandasCatalog.instantiate(), PandasCatalog)


def test_expand_paths_echoes_paths() -> None:
    """Plain file names are handed back as they are, and naming a file twice only
    counts once. There is nothing to look up for them.
    """
    assert PandasCatalog().expand_paths(["a.csv", "b.csv", "a.csv"]) == {
        "a.csv",
        "b.csv",
    }


def test_csv_roundtrip(tmp_path: Path) -> None:
    """We write a small frame to CSV and read it back. The names and numbers should
    come out the same, so nothing gets lost on the way.
    """
    df = _roundtrip(tmp_path / "x.csv")
    assert list(df["name"]) == ["a", "b"]
    assert list(df["n"]) == [1, 2]


def test_parquet_roundtrip(tmp_path: Path) -> None:
    """Same round trip as CSV, this time through Parquet. The names and numbers should
    come back unchanged.
    """
    df = _roundtrip(tmp_path / "x.parquet")
    assert list(df["name"]) == ["a", "b"]
    assert list(df["n"]) == [1, 2]


def test_xlsx_roundtrip(tmp_path: Path) -> None:
    """Excel files should round trip too, with the same names coming back. The test
    skips itself when openpyxl is not installed.
    """
    pytest.importorskip("openpyxl")
    df = _roundtrip(tmp_path / "x.xlsx")
    assert list(df["name"]) == ["a", "b"]


def test_read_unsupported_extension_raises(tmp_path: Path) -> None:
    """Reading a txt file is not supported, and it should fail with a clear error.
    Quietly guessing a format would only cause confusing failures later.
    """
    with pytest.raises(ValueError, match="Unsupported file extension"):
        PandasCatalog().read_df(str(tmp_path / "x.txt"))


def test_write_unsupported_extension_raises(tmp_path: Path) -> None:
    """Writing to a txt path is not supported either, and should fail with the same
    clear error rather than guess.
    """
    df: DataFrame = _write_source(tmp_path)
    with pytest.raises(ValueError, match="Unsupported file extension"):
        PandasCatalog().write_df(df, str(tmp_path / "x.txt"))


def test_read_no_extension_raises(tmp_path: Path) -> None:
    """A path with no extension gives us no clue what kind of file it is. Reading it
    should fail with the same clear error.
    """
    with pytest.raises(ValueError, match="Unsupported file extension"):
        PandasCatalog().read_df(str(tmp_path / "noext"))


def test_dotted_csv_name(tmp_path: Path) -> None:
    """A name like report.2024.csv has extra dots in it. Its extension is still csv, so
    it should round trip without trouble.
    """
    _roundtrip(tmp_path / "report.2024.csv")


def test_dotted_parquet_name(tmp_path: Path) -> None:
    """A name like data.v1.parquet has an extra dot too. The extension is still
    parquet, so it should round trip fine.
    """
    _roundtrip(tmp_path / "data.v1.parquet")


def test_uppercase_extension(tmp_path: Path) -> None:
    """A file called X.CSV still counts as CSV. Exports from other systems often shout
    their extensions.
    """
    _roundtrip(tmp_path / "X.CSV")


def test_expand_paths_expands_globs_and_regexes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In a folder with two CSVs and a text file, a star glob and a re: pattern both
    pick out the two CSVs. That is how a user names many files in one go.
    """
    for name in ("a.csv", "b.csv", "c.txt"):
        (tmp_path / name).write_text("x")
    monkeypatch.chdir(tmp_path)

    assert PandasCatalog().expand_paths(["*.csv"]) == {"a.csv", "b.csv"}
    assert PandasCatalog().expand_paths([r"re:[ab]\.csv"]) == {"a.csv", "b.csv"}
