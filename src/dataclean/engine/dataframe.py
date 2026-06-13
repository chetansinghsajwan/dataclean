from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Literal, Mapping

DataType = Literal[
    "str",
    "bool",
    "int",
    "float",
    "double",
]


@dataclass(frozen=True)
class DataReader:
    fn: Callable[str | bool | int | float | None, ...]
    cols: tuple[str, ...]


@dataclass(frozen=True)
class DataWriter:
    expr: (
        Callable[str | bool | int | float | None, ...] | str | bool | int | float | None
    )
    read_cols: tuple[str, ...]
    write_cols: tuple[tuple[str, DataType], ...]


class DataFrame(ABC):
    @abstractmethod
    def supports(df: Any) -> bool:
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
