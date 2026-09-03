from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from dataclean.types import checked


class DataType(StrEnum):
    STR = "str"
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    DOUBLE = "double"

    def __repr__(self):
        return str(self.value)


DataTypeValues = str | bool | int | float | None


@checked
@dataclass
class DataReader:
    # Accept any callable shape; engines will validate at runtime
    fn: Callable[..., None]
    cols: tuple[str, ...]


@checked
@dataclass
class DataWriter:
    expr: (
        Callable[
            ...,
            str
            | bool
            | int
            | float
            | None
            | tuple[str | bool | int | float | None, ...],
        ]
        | str
        | bool
        | int
        | float
        | None
        | tuple[str | bool | int | float | None, ...]
    )
    read_cols: tuple[str, ...]
    write_cols: tuple[tuple[str, DataType], ...]


Aggregator = Callable


class Aggregators:
    def _count(*args, **kwargs) -> int:
        return len(args)

    count: Aggregator = _count


@checked
@dataclass
class DataFrame(ABC):
    # Optional reference to the underlying raw dataframe for engine adapters and tests
    df: Any | None = None

    @staticmethod
    @abstractmethod
    def supports(df: Any) -> bool:
        """Return True when this API implementation can wrap the given raw dataframe."""
        pass

    def col_names(self) -> Iterator[str]:
        return (col for col, _ in self.cols())

    @abstractmethod
    def cols(self) -> tuple[tuple[str, DataType], ...]:
        pass

    @abstractmethod
    def rename_cols(self, rename_map: Mapping[str, str]):
        pass

    @abstractmethod
    def read_cols(self, readers: Iterable[DataReader]):
        pass

    @abstractmethod
    def write_cols(self, writers: Iterable[DataWriter]):
        pass

    @abstractmethod
    def remove_cols(self, cols: Iterable[str]):
        pass

    @abstractmethod
    def cast_cols(self, cols: Mapping[str, DataType]):
        pass

    @abstractmethod
    def group_by(self, cols: Iterable[str]) -> "DataFrame":
        pass

    @abstractmethod
    def agg(
        self, cols: Mapping[str, Aggregator] | Iterable[Aggregator] | Aggregator
    ) -> "DataFrame":
        pass

    @abstractmethod
    def distinct(self, cols: Iterable[str] | None = None) -> "DataFrame":
        pass

    @abstractmethod
    def count(self) -> int:
        pass

    @abstractmethod
    def collect(self) -> list[tuple[DataTypeValues, ...]]:
        pass

    @abstractmethod
    def select(self, cols: str | Iterable[str]) -> "DataFrame":
        "Single column or list of columns to select."
        pass

    @abstractmethod
    def strip(self, cols: str | Iterable[str] | None = None) -> "DataFrame":
        "Single column or list of columns to strip whitespace from."
        pass

    @abstractmethod
    def nullif(self, cols: str | Iterable[str] | None = None) -> "DataFrame":
        "Replace the value with null if the value is empty. If cols is None, apply to all string columns."
        pass

    @abstractmethod
    def order_by(self, cols: str | Iterable[str], desc: bool = False) -> "DataFrame":
        "If cols is None, apply to all columns."
        pass

    @abstractmethod
    def limit(self, n: int) -> "DataFrame":
        pass

    @abstractmethod
    def filter_null(self, cols: str | Iterable[str] | None = None) -> "DataFrame":
        "If cols is None, apply to all columns."
        pass
