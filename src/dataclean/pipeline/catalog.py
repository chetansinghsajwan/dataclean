"""Catalog for registering and discovering cleaners."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from dataclean.cleaners.cleaner import Cleaner


class Catalog(ABC):
    """Abstract base for platform-specific cleaner registries."""

    @abstractmethod
    def get_cleaners(self) -> Sequence[Cleaner]:
        """Return all available cleaners for this platform."""
        pass


class DefaultCatalog(Catalog):
    """Default catalog with all built-in cleaners."""

    def get_cleaners(self) -> Sequence[Cleaner]:
        """Return all built-in cleaners."""
        from dataclean.cleaners.address_cleaner import AddressCleaner
        from dataclean.cleaners.bool_cleaner import BoolCleaner
        from dataclean.cleaners.country_cleaner import CountryCleaner
        from dataclean.cleaners.datetime_cleaner import DateTimeCleaner
        from dataclean.cleaners.email_cleaner import EmailCleaner
        from dataclean.cleaners.gender_cleaner import GenderCleaner
        from dataclean.cleaners.numeric_cleaner import NumericCleaner
        from dataclean.cleaners.phone_cleaner import PhoneCleaner
        from dataclean.cleaners.text_cleaner import TextCleaner
        from dataclean.cleaners.uuid_cleaner import UuidCleaner

        return (
            # Group cleaners (processed first)
            AddressCleaner(),
            # Base cleaners
            PhoneCleaner(),
            CountryCleaner(),
            EmailCleaner(),
            BoolCleaner(),
            DateTimeCleaner(),
            GenderCleaner(),
            NumericCleaner(),
            TextCleaner(),
            UuidCleaner(),
        )
