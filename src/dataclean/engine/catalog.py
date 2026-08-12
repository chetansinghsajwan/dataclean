from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar, Self

from dataclean.engine.dataframe import DataFrame
from dataclean.types import checked


@checked
class CatalogPriority(IntEnum):
    GENERIC = 0
    ENV_DEPENDENT = 50


@checked
@dataclass
class Catalog(ABC):
    priority: ClassVar[int] = CatalogPriority.GENERIC

    @classmethod
    def supports_env(cls) -> bool:
        return False

    @classmethod
    def instantiate(cls) -> Self | None:
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
