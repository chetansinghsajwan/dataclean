"""Ibis-backed implementation of the dataclean ``Catalog`` API, via DuckDB."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Self, override

import ibis
import ibis.backends.duckdb

from dataclean import Catalog, DataFrame
from dataclean.types import checked
from dataclean_ibis.dataframe import IbisDataFrame

_READERS: dict[str, str] = {".csv": "read_csv", ".parquet": "read_parquet"}
_WRITERS: dict[str, str] = {".csv": "to_csv", ".parquet": "to_parquet"}


@checked
@dataclass
class IbisCatalog(Catalog):
    """Local file catalog backed by an embedded DuckDB connection.

    Supports ``.csv`` and ``.parquet`` files only. DuckDB has no native
    Excel reader/writer; bridging ``.xlsx``/``.xls`` support would mean
    routing through pandas, reintroducing an eager dependency this
    DuckDB-native catalog is meant to avoid.
    """

    con: ibis.backends.duckdb.Backend

    READERS: ClassVar[dict[str, str]] = _READERS
    WRITERS: ClassVar[dict[str, str]] = _WRITERS

    @override
    @classmethod
    def supports_env(cls) -> bool:
        # DuckDB is embedded and a hard dependency of this plugin; it needs
        # no external service or credentials, so it is always usable.
        return True

    @override
    @classmethod
    def instantiate(cls) -> Self:
        return cls(con=ibis.duckdb.connect())

    @override
    def expand_paths(self, paths: Iterable[str]) -> set[str]:
        return set(paths)

    @override
    def read_df(self, path: str) -> IbisDataFrame:
        ext = self._extension_of(path)
        if ext not in self.READERS:
            raise ValueError(f"Unsupported file extension: {ext}")
        table = getattr(self.con, self.READERS[ext])(path)
        return IbisDataFrame(df=table)

    @override
    def write_df(self, df: DataFrame, path: str) -> None:
        assert isinstance(df, IbisDataFrame), (
            f"IbisCatalog can only write IbisDataFrame, got {type(df)}"
        )
        ext = self._extension_of(path)
        if ext not in self.WRITERS:
            raise ValueError(f"Unsupported file extension: {ext}")
        getattr(self.con, self.WRITERS[ext])(df.df, path)

    @staticmethod
    def _extension_of(path: str) -> str:
        suffixes = Path(path).suffixes
        return suffixes[0] if suffixes else ""
