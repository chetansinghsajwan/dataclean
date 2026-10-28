"""The Catalog abstraction for resolving paths to and from dataframes.

Defines :class:`Catalog`, the abstract base class implemented by
data-source integrations (e.g. a filesystem, a data lake, a specific
storage backend) so that :func:`dataclean.clean_paths` can expand path
patterns and read/write dataframes without knowing the storage details.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar, Self

from dataclean.types import checked

from .dataframe import DataFrame


@checked
@dataclass
class Catalog(ABC):
    """Abstract data-source integration: resolves paths to/from dataframes.

    Subclasses implement path expansion (e.g. glob patterns, table
    listings) and reading/writing dataframes for a particular storage
    backend, so that :func:`dataclean.clean_paths` can operate generically
    across data sources.

    Paths are routed to catalogs by scheme prefix: ``scheme:rest`` goes to
    the catalog whose ``schemes`` contains ``scheme``, and receives only
    ``rest``. A path with no ``:`` goes to the catalog that lists the empty
    scheme ``""``. A scheme may belong to only one registered catalog.

    Attributes:
        schemes: Path scheme prefixes this catalog handles (without the
            ``:``). Include ``""`` to be the default for unprefixed paths.
    """

    schemes: ClassVar[tuple[str, ...]] = ()

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
