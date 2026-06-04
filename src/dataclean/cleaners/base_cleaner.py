from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class BaseCleaner(ABC):
    inplace: bool = True
    split_components: bool = False

    @abstractmethod
    def clean_value(self, v: str) -> str | None:
        """
        Clean the input value and return the cleaned value.
        If the value cannot be cleaned, return None.

        This method must be implemented by subclasses to provide specific cleaning logic for different types of data.

        Args:
            v (str): The input value to be cleaned.

        Returns:
            str | None: The cleaned value, or None if the value cannot be cleaned.
        """

        pass
