"""The DataFrame abstraction that engine adapters implement.

Defines :class:`DataFrame`, the abstract base class that every concrete
engine adapter (e.g. pandas, PySpark, Databricks) implements to provide a
uniform, engine-agnostic column API to the rest of dataclean (cleaners,
pipeline, catalogs). Also defines the shared :class:`DataType` enum and the
:class:`DataReader`/:class:`DataWriter` descriptors used to declaratively
read from and write to columns.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from dataclean.types import checked


class DataType(StrEnum):
    """Engine-agnostic logical column data type.

    Used throughout dataclean (cleaners, pipeline, engine adapters) to
    describe and request column types independently of any particular
    dataframe engine's native dtype system. Each member's value is the
    lowercase name used when the type needs to be rendered as a string.

    Attributes:
        STR: Text/string data.
        BOOL: Boolean (true/false) data.
        INT: Integer numeric data.
        FLOAT: Single-precision floating point numeric data.
        DOUBLE: Double-precision floating point numeric data.
    """

    STR = "str"
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    DOUBLE = "double"

    def __repr__(self):
        """Return the same plain value string as ``str()``, not enum repr."""
        return str(self.value)


DataTypeValues = str | bool | int | float | None
"""The union of Python types a single cell value may hold, per :class:`DataType`."""


@checked
@dataclass
class DataReader:
    """Declarative request to read one or more columns via a callback.

    Passed to :meth:`DataFrame.read_cols` so an engine adapter can invoke
    ``fn`` once per row, passing each of ``cols`` as a positional argument,
    without the caller needing to know how the underlying engine iterates
    rows.

    Attributes:
        fn: Callable invoked with one positional argument per column in
            ``cols`` (in order), for side effects only; its return value is
            ignored. Any callable shape is accepted here — the engine
            adapter validates the call at runtime.
        cols: Names of the columns whose values are passed to ``fn``.
    """

    # Accept any callable shape; engines will validate at runtime
    fn: Callable[..., None]
    cols: tuple[str, ...]


@checked
@dataclass
class DataWriter:
    """Declarative request to compute and write one or more columns.

    Passed to :meth:`DataFrame.write_cols` so an engine adapter can compute
    new/updated column values from existing ones. ``expr`` is evaluated per
    row (called with one positional argument per column in ``read_cols``)
    and its result is written to the column(s) named in ``write_cols``; a
    single write column expects a scalar result, multiple write columns
    expect a tuple of results in matching order. ``expr`` may also be a
    constant scalar/tuple instead of a callable, which is broadcast to
    every row.

    Attributes:
        expr: Callable computing the new value(s) from the ``read_cols``
            values, or a constant scalar/tuple broadcast to all rows.
        read_cols: Names of the columns whose values are passed to ``expr``.
        write_cols: Names and :class:`DataType` of the columns to write,
            in the order ``expr``'s result should be unpacked into.
    """

    expr: (
        Callable[
            ...,
            str
            | bool
            | int
            | float
            | None
            | tuple[str | bool | int | float | None, ...],
        ]
        | str
        | bool
        | int
        | float
        | None
        | tuple[str | bool | int | float | None, ...]
    )
    read_cols: tuple[str, ...]
    write_cols: tuple[tuple[str, DataType], ...]


Aggregator = Callable
"""A callable usable as an aggregation function with :meth:`DataFrame.agg`."""


class Aggregators:
    """Namespace of built-in :data:`Aggregator` callables for :meth:`DataFrame.agg`."""

    def _count(*args, **kwargs) -> int:
        """Return the number of positional arguments received."""
        return len(args)

    count: Aggregator = _count
    """Aggregator that counts the number of values (rows) in a group."""


@checked
@dataclass
class DataFrame(ABC):
    """Abstract, engine-agnostic API for reading and transforming a dataframe.

    Concrete subclasses (one per supported dataframe engine, e.g. pandas or
    PySpark) wrap a native dataframe object and expose it through this
    uniform column-oriented interface, so that cleaners and the pipeline can
    operate without depending on any specific engine. Most methods mutate
    the wrapped dataframe in place; ``group_by``/``agg``/``distinct``/
    ``select``/``strip``/``nullif``/``order_by``/``limit``/``filter_null``
    return a (possibly new) :class:`DataFrame` to support chaining.

    Attributes:
        df: The underlying native dataframe object being wrapped, or
            ``None``. Primarily useful for engine adapters and tests that
            need to reach the raw object.
    """

    # Optional reference to the underlying raw dataframe for engine adapters and tests
    df: Any | None = None

    @staticmethod
    @abstractmethod
    def supports(df: Any) -> bool:
        """Return True when this API implementation can wrap the given raw dataframe."""
        pass

    def col_names(self) -> Iterator[str]:
        """Iterate over the names of all columns, in :meth:`cols` order."""
        return (col for col, _ in self.cols())

    @abstractmethod
    def cols(self) -> tuple[tuple[str, DataType], ...]:
        """Return the (name, :class:`DataType`) pairs for every column, in order."""
        pass

    @abstractmethod
    def rename_cols(self, rename_map: Mapping[str, str]):
        """Rename columns in place according to ``rename_map`` (old name -> new name)."""
        pass

    @abstractmethod
    def read_cols(self, readers: Iterable[DataReader]):
        """Invoke each :class:`DataReader`'s callback over the dataframe's rows.

        Does not mutate the dataframe; used for side effects such as
        collecting statistics or logging.
        """
        pass

    @abstractmethod
    def write_cols(self, writers: Iterable[DataWriter]):
        """Compute and write columns in place per each :class:`DataWriter`."""
        pass

    @abstractmethod
    def remove_cols(self, cols: Iterable[str]):
        """Drop the given columns from the dataframe in place."""
        pass

    @abstractmethod
    def cast_cols(self, cols: Mapping[str, DataType]):
        """Cast the given columns in place to the paired :class:`DataType`."""
        pass

    @abstractmethod
    def group_by(self, cols: Iterable[str]) -> "DataFrame":
        """Return a new :class:`DataFrame` grouped by the given columns."""
        pass

    @abstractmethod
    def agg(
        self, cols: Mapping[str, Aggregator] | Iterable[Aggregator] | Aggregator
    ) -> "DataFrame":
        """Return a new :class:`DataFrame` with the given aggregation(s) applied.

        Args:
            cols: Either a mapping of column name to :data:`Aggregator`, an
                iterable of aggregators to apply, or a single aggregator.
        """
        pass

    @abstractmethod
    def distinct(self, cols: Iterable[str] | None = None) -> "DataFrame":
        """Return a new :class:`DataFrame` with duplicate rows removed.

        Args:
            cols: Columns to consider when determining uniqueness. If
                ``None``, all columns are considered.
        """
        pass

    @abstractmethod
    def count(self) -> int:
        """Return the number of rows."""
        pass

    @abstractmethod
    def collect(self) -> list[tuple[DataTypeValues, ...]]:
        """Materialize and return all rows as a list of value tuples."""
        pass

    @abstractmethod
    def select(self, cols: str | Iterable[str]) -> "DataFrame":
        """Return a new :class:`DataFrame` containing only the given column(s).

        Args:
            cols: Single column or list of columns to select.
        """
        pass

    @abstractmethod
    def strip(self, cols: str | Iterable[str] | None = None) -> "DataFrame":
        """Return a new :class:`DataFrame` with whitespace stripped from column(s).

        Args:
            cols: Single column or list of columns to strip whitespace
                from. If ``None``, applies to all string columns.
        """
        pass

    @abstractmethod
    def nullif(self, cols: str | Iterable[str] | None = None) -> "DataFrame":
        """Return a new :class:`DataFrame` with empty values replaced by null.

        Args:
            cols: Single column or list of columns to check. If ``None``,
                applies to all string columns.
        """
        pass

    @abstractmethod
    def order_by(self, cols: str | Iterable[str], desc: bool = False) -> "DataFrame":
        """Return a new :class:`DataFrame` sorted by the given column(s).

        Args:
            cols: Single column or list of columns to sort by. If ``None``,
                apply to all columns.
            desc: If True, sort in descending order. Defaults to False.
        """
        pass

    @abstractmethod
    def limit(self, n: int) -> "DataFrame":
        """Return a new :class:`DataFrame` containing at most ``n`` rows."""
        pass

    @abstractmethod
    def filter_null(self, cols: str | Iterable[str] | None = None) -> "DataFrame":
        """Return a new :class:`DataFrame` with rows containing null values removed.

        Args:
            cols: Single column or list of columns to check for null
                values. If ``None``, apply to all columns.
        """
        pass
