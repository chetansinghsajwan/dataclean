"""The Catalog abstraction for resolving paths to and from dataframes.

Defines :class:`Catalog`, the abstract base class implemented by
data-source integrations (e.g. a filesystem, a data lake, a specific
storage backend) so that :func:`dataclean.clean_paths` can expand path
patterns and read/write dataframes without knowing the storage details.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar, Self

from dataclean.types import checked

from .dataframe import DataFrame


@checked
class CatalogPriority(IntEnum):
    """Relative ordering used when auto-selecting a catalog from the environment.

    Catalog types registered in :class:`~dataclean.config.Config` are tried
    in descending priority order (highest first) when no explicit catalog
    is given and one must be auto-detected via :meth:`Catalog.supports_env`.

    Attributes:
        GENERIC: Default priority for catalogs with no special environment
            requirements.
        ENV_DEPENDENT: Higher priority for catalogs that depend on specific
            environment variables/conditions and should be preferred over
            generic catalogs when applicable.
    """

    GENERIC = 0
    ENV_DEPENDENT = 50


@checked
@dataclass
class Catalog(ABC):
    """Abstract data-source integration: resolves paths to/from dataframes.

    Subclasses implement path expansion (e.g. glob patterns, table
    listings) and reading/writing dataframes for a particular storage
    backend, so that :func:`dataclean.clean_paths` can operate generically
    across data sources.

    Attributes:
        priority: Class-level :class:`CatalogPriority` used to order this
            catalog type among others when auto-selecting one from the
            environment. Defaults to ``CatalogPriority.GENERIC``.
    """

    priority: ClassVar[int] = CatalogPriority.GENERIC

    @classmethod
    def supports_env(cls) -> bool:
        """Return True if this catalog can be auto-instantiated from the current environment."""
        return False

    @classmethod
    def instantiate(cls) -> Self | None:
        """Construct an instance of this catalog from the environment, or None if not possible."""
        return None

    @abstractmethod
    def expand_paths(self, paths: Iterable[str]) -> set[str]:
        """Expand path patterns (e.g. globs) into the concrete set of paths they match."""
        pass

    @abstractmethod
    def read_df(self, path: str) -> DataFrame:
        """Read the data at ``path`` and return it as a :class:`DataFrame`."""
        pass

    @abstractmethod
    def write_df(self, df: DataFrame, path: str) -> None:
        """Write ``df`` to ``path``."""
        pass
