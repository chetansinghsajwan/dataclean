from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Self

from dataclean.engine.dataframe import DataFrame
from dataclean.types import checked


@checked
@dataclass
class Catalog(ABC):
    def supports_env() -> bool:
        return False

    def instantiate() -> Self | None:
        return None

    @abstractmethod
    def expand_paths(self, paths: Iterable[str]) -> set[str]:
        pass

    @abstractmethod
    def read_df(self, path: str) -> DataFrame:
        pass

    @abstractmethod
    def write_df(self, df: DataFrame, path: str) -> None:
        pass
