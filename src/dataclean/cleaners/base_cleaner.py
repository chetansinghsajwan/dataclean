from abc import ABC, abstractmethod
from collections.abc import Mapping

from dataclean.engine.dataframe import DataFrame, DataType
from dataclean.types import StrictBaseModel


class CellValue(str):
    """Type alias for cell values in dataframes."""

    pass


class ContextRequest(StrictBaseModel, frozen=True):  # ty: ignore[invalid-frozen-dataclass-subclass]
    """Request for context (e.g., country for phone cleaning)."""

    role: str
    required: bool = False


class CleanContext(StrictBaseModel, frozen=True):  # ty: ignore[invalid-frozen-dataclass-subclass]
    """Context values available for a cleaner during execution."""

    values: Mapping[str, CellValue | None]


class Cleaner(StrictBaseModel, ABC, frozen=True):  # ty: ignore[invalid-frozen-dataclass-subclass]
    """Base abstract class for all cleaners."""

    def provided_roles(self) -> tuple[str, ...]:
        """Semantic role(s) this cleaner's output represents."""
        return ()


class BaseCleaner(Cleaner, ABC, frozen=True):
    """Base cleaner for single primary column cleaning."""

    inplace: bool = True
    split_components: bool = False

    @abstractmethod
    def name(self) -> str:
        """Return the name of this cleaner."""
        pass

    @abstractmethod
    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]:
        """Return the output schema of cleaned data."""
        pass

    @abstractmethod
    def clean_value(
        self, value: str, context: CleanContext | None = None
    ) -> CellValue | None:
        """
        Clean the input value and return the cleaned value.
        If the value cannot be cleaned, return None.

        Args:
            value: The input value to be cleaned.
            context: Optional context from dependent cleaners.

        Returns:
            Cleaned value, or None if the value cannot be cleaned.
        """
        pass

    @abstractmethod
    def get_data_type_confidence(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        """Score confidence that this cleaner matches the given columns."""
        pass

    def context_requests(self) -> tuple[ContextRequest, ...]:
        """Return context (role) dependencies required for this cleaner."""
        return ()
