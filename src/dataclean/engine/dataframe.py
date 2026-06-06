from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Callable, Mapping


class DataFrame(ABC):
    DataReader = tuple[Callable, *tuple[str, ...]]

    @abstractmethod
    def supports(df: any) -> bool:
        pass

    @abstractmethod
    def cols(self) -> tuple[str]:
        pass

    @abstractmethod
    def rename_cols(self, rename_map: Mapping[str, str]):
        pass

    @abstractmethod
    def read_cols(self, cols: Mapping[str, DataReader]):
        pass

    def read_col(self, reader: DataReader):
        self.read_cols((reader,))

    @abstractmethod
    def add_cols(self, cols: Mapping[str, any]):
        pass

    @abstractmethod
    def remove_cols(self, cols: Iterable[str]):
        pass
