"""Incremental cleaning of slowly changing dimension (SCD type 2) tables.

An SCD 2 table keeps one row per version of a record: a new version opens
with ``scd_from`` and ``scd_active`` true, and when it is replaced the old
row is closed (``scd_to`` set, ``scd_active`` false). :class:`Scd2` tells
:func:`dataclean.clean_paths` which columns carry that history, so a rerun
cleans only the versions that are new or were closed since the last run.
"""

from dataclasses import dataclass

from dataclean.engine.dataframe import DataFrame
from dataclean.types import checked


@checked
@dataclass(frozen=True)
class Scd2:
    """Names the history columns of an SCD 2 table.

    Decision: the history columns and the keys are never cleaned. They are
    how a source row is matched with its already cleaned copy, so cleaning
    them in place would make the two stop matching.

    Attributes:
        key_cols: Columns that identify a record across its versions.
        active_col: Boolean column, true on the current version.
        from_col: Timestamp column where a version became effective.
        to_col: Timestamp column where a version stopped being effective, or
            ``None`` if the table has none.
    """

    key_cols: tuple[str, ...]
    active_col: str = "scd_active"
    from_col: str = "scd_from"
    to_col: str | None = "scd_to"

    def __post_init__(self) -> None:
        """Reject a config without keys."""
        if not self.key_cols:
            raise ValueError("Scd2 needs at least one key column")

    @property
    def protected_cols(self) -> tuple[str, ...]:
        """The columns cleaning must leave alone."""
        extra = (self.to_col,) if self.to_col else ()
        return (*self.key_cols, self.active_col, self.from_col, *extra)

    @property
    def _version_cols(self) -> tuple[str, ...]:
        """A version of a record: its keys and when it became effective."""
        return (*self.key_cols, self.from_col)

    @property
    def _state_cols(self) -> tuple[str, ...]:
        """A version and whether it is current, which changes when it closes."""
        return (*self._version_cols, self.active_col)

    def check(self, df: DataFrame, what: str) -> None:
        """Raise if ``df`` lacks a column this config names.

        Args:
            df: The dataframe to check.
            what: What the dataframe is, for the error message.

        Raises:
            ValueError: If a protected column is missing.
        """
        missing = [c for c in self.protected_cols if c not in set(df.col_names())]
        if missing:
            raise ValueError(f"{what} is missing SCD columns: {missing}")

    def pending(self, source: DataFrame, cleaned: DataFrame) -> DataFrame:
        """Return the source rows still to clean.

        A row is pending when its version is not in the cleaned data yet, or
        is there with a different ``active_col``, i.e. it has closed since.
        """
        return source.anti_join(cleaned, self._state_cols)

    def merge(self, cleaned: DataFrame, fresh: DataFrame) -> DataFrame:
        """Return the cleaned data with ``fresh`` rows added in place of older copies."""
        return cleaned.anti_join(fresh, self._version_cols).union(fresh)
