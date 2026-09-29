"""Presets: reusable, matchable bundles of cleaners for a dataframe's columns."""

from abc import ABC, abstractmethod

from dataclean.cleaners import Cleaner
from dataclean.types import checked


@checked
class Preset(ABC):
    """Abstract bundle of cleaners that can be scored against a dataframe's columns.

    Subclasses implement :meth:`match` to score how well this preset fits a
    given set of columns, and :meth:`get` to return the concrete cleaner
    assignment it proposes for those columns.
    """

    class MatchContext:
        """Information available to :meth:`Preset.match` when scoring a preset.

        Attributes:
            cols: Names of the columns being matched against.
        """

        cols: list[str]

    @abstractmethod
    def match(self, ctx: MatchContext) -> float:
        """Return a score for how well this preset fits ``ctx.cols``.

        Higher scores indicate a better fit; used to select among
        candidate presets.
        """
        pass

    @abstractmethod
    def get(self) -> dict[str, Cleaner]:
        """Return this preset's cleaner assignment, mapping column name to :class:`Cleaner`."""
        pass
