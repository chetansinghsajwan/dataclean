from abc import ABC, abstractmethod

from dataclean.cleaners import Cleaner
from dataclean.types import checked


@checked
class Preset(ABC):
    class MatchContext:
        cols: list[str]

    @abstractmethod
    def match(self, ctx: MatchContext) -> float:
        pass

    @abstractmethod
    def get(self) -> dict[str, Cleaner]:
        pass
