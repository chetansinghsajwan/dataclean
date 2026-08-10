import importlib.util
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Self, override

import pandas as pd

from dataclean.engine.catalog import Catalog
from dataclean.engine.dataframe import DataFrame
from dataclean.types import checked
from dataclean_pandas.dataframe import PandasDataFrame


@checked
@dataclass
class PandasCatalog(Catalog):
    READERS = {
        ".csv": pd.read_csv,
        ".parquet": pd.read_parquet,
        ".xlsx": lambda p: pd.read_excel(p, engine="openpyxl"),
        ".xls": lambda p: pd.read_excel(p, engine="xlrd"),
    }

    WRITERS = {
        ".csv": lambda df, p: df.to_csv(p),
        ".parquet": lambda df, p: df.to_parquet(p),
        ".xlsx": lambda df, p: df.to_excel(p, engine="openpyxl"),
        ".xls": lambda df, p: df.to_excel(p, engine="xlrd"),
    }

    @override
    @classmethod
    def supports_env(cls) -> bool:
        # Pandas is installed as a dependency
        return True

    @override
    @classmethod
    def instantiate(cls) -> Self:
        return cls()

    @override
    def expand_paths(self, paths: Iterable[str]) -> set[str]:
        return set(paths)

    @override
    def read_df(self, path: str) -> PandasDataFrame:
        suffixes = Path(path).suffixes
        ext = suffixes[0] if suffixes else ""

        if ext not in self.READERS:
            raise ValueError(f"Unsupported file extension: {ext}")

        # pandas auto-detects .gz/.bz2/.xz/.zip from filename
        pdf = self.READERS[ext](path)
        return PandasDataFrame(pdf)

    @override
    def write_df(self, df: DataFrame, path: str) -> None:
        suffixes = Path(path).suffixes
        ext = suffixes[0] if suffixes else ""

        if ext not in self.WRITERS:
            raise ValueError(f"Unsupported file extension: {ext}")

        self.WRITERS[ext](df, path)
