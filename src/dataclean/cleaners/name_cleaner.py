"""Cleaner that recognizes personal-name columns and nulls placeholder values."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar, override

from dataclean.engine import DataFrame, DataType
from dataclean.types import checked
from dataclean.utils import is_null_token, null_token_set, strip_html

from .cleaner import Cleaner


@checked
@dataclass
class NameCleaner(Cleaner):
    """Recognizes personal-name columns and passes their values through.

    For now this cleaner only takes part in auto-detection: it claims
    person-name columns (``fname``, ``lname``, ``mname``, ``first_name``,
    ``surname``, ``full_name``, ...) so that no other cleaner does, and
    returns each value unchanged, except that a placeholder such as ``n/a`` or
    ``-`` becomes null. Values still get the pipeline's input
    normalization like any other cleaner (surrounding whitespace is
    stripped, blank strings become null). Casing is deliberately not
    touched: person-name fields often hold acronyms, initials and company
    names that title-casing would damage.

    Only string columns are matched, and a bare ``name`` column is not
    (it is often a company or product name).

    Attributes:
        null_tokens: Placeholder values (compared case-insensitively) that
            become null. ``na`` and ``nan`` are left out of the default, since
            they are real names.
    """

    null_tokens: tuple[str, ...] = ("null", "none", "undefined", "n/a", "-")

    # Short forms must stand alone (or be concatenated, e.g. "lnamefname") so
    # that "colname" or "filename" never match.
    _SHORT_NAME_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"(?:^|[^a-z])(?:[flm]name)+(?:$|[^a-z])"
    )
    _LONG_NAME_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"first_?name|last_?name|middle_?name|full_?name|given_?name|"
        r"family_?name|maiden_?name|forename|surname"
    )

    _null_set: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Initialize base cleaner state and build the placeholder lookup."""
        super().__post_init__()
        self._null_set = null_token_set(self.null_tokens)

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore
        """Return ``v`` without HTML, or None if it is a placeholder.

        Args:
            v: The name value (already stripped and non-blank).

        Returns:
            ``v`` with any HTML tags removed (and the spaces they leave
            collapsed), or None if nothing is left or it is one of
            ``null_tokens``.
        """
        stripped = strip_html(v)
        if stripped != v:
            v = " ".join(stripped.split())
        return None if is_null_token(v, self._null_set) else v

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
