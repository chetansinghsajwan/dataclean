from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dataclean.cleaners.base_cleaner import CellValue, Cleaner
from dataclean.engine.dataframe import DataType

if TYPE_CHECKING:
    from dataclean.cleaners.base_cleaner import BaseCleaner


@dataclass(frozen=True)
class ColumnRole:
    """Defines a role that a cleaner group requires."""

    key: str
    required: bool = True
    detector: "BaseCleaner | None" = (
        None  # reuse an existing cleaner's confidence scoring
    )
    name_hints: tuple[str, ...] = ()  # fallback keyword match


class GroupCleaner(Cleaner, ABC, frozen=True):
    """Base cleaner for multi-column group cleaning (e.g., address cleaning)."""

    @abstractmethod
    def name(self) -> str:
        """Return the name of this cleaner."""
        pass

    @abstractmethod
    def output_schema(self) -> tuple[tuple[str, DataType], ...]:
        """Return the output schema as ordered (name, type) tuples."""
        pass

    @abstractmethod
    def input_roles(self) -> tuple[ColumnRole, ...]:
        """Return the roles (columns) required as input."""
        pass

    @abstractmethod
    def clean_row(
        self, values: Mapping[str, CellValue | None]
    ) -> tuple[CellValue | None, ...] | None:
        """
        Clean a row of values and return cleaned values.
        values maps role.key -> cell value for the current row.
        Returns tuple of cleaned values in same order as output_schema(),
        or None if cleaning failed.
        """
        pass

    @abstractmethod
    def group_confidence(self, role_scores: Mapping[str, float]) -> float:
        """Compute confidence that all matched roles belong to this group."""
        pass
