"""Cleaner that recognizes personal-name columns; it does not alter the values."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar, override

from dataclean.engine import DataFrame, DataType
from dataclean.types import checked

from .cleaner import Cleaner


@checked
@dataclass
class NameCleaner(Cleaner):
    """Recognizes personal-name columns and passes their values through.

    For now this cleaner only takes part in auto-detection: it claims
    person-name columns (``fname``, ``lname``, ``mname``, ``first_name``,
    ``surname``, ``full_name``, ...) so that no other cleaner does, and
    returns each value unchanged. Values still get the pipeline's input
    normalization like any other cleaner (surrounding whitespace is
    stripped, blank strings become null). Casing is deliberately not
    touched: person-name fields often hold acronyms, initials and company
    names that title-casing would damage.

    Only string columns are matched, and a bare ``name`` column is not
    (it is often a company or product name).
    """

    # Short forms must stand alone (or be concatenated, e.g. "lnamefname") so
    # that "colname" or "filename" never match.
    _SHORT_NAME_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"(?:^|[^a-z])(?:[flm]name)+(?:$|[^a-z])"
    )
    _LONG_NAME_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"first_?name|last_?name|middle_?name|full_?name|given_?name|"
        r"family_?name|maiden_?name|forename|surname"
    )

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore
        """Return ``v`` unchanged.

        Args:
            v: The name value (already stripped and non-blank).

        Returns:
            ``v``.
        """
        return v

    @override
    def match_score(self, df: DataFrame, cols: Iterable[str]) -> float:
        """Score confidence from the column name looking like a person's name.

        Args:
            df: The dataframe being inspected; used only to skip columns that
                are known not to be strings.
            cols: Candidate column name(s); only the first is considered.

        Returns:
            1.0 if the column is a string (or unknown-typed) column whose
            name is a person-name column, otherwise 0.0.
        """
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0

        column = cols_tuple[0]
        if dict(df.cols()).get(column) not in (None, DataType.STR):
            return 0.0

        name = column.lower()
        if self._SHORT_NAME_RE.search(name) or self._LONG_NAME_RE.search(name):
            return 1.0

        return 0.0
