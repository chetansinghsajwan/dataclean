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
