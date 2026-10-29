"""Cleaner for normalizing personal names (first, middle, last, full)."""

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
    """Normalizes personal names: whitespace, casing, particles and suffixes.

    Names that are entirely upper- or lower-case are re-cased word by word
    (``"JOHN o'neil"`` style input is left alone, see
    ``preserve_mixed_case``). Re-casing handles hyphenated and apostrophe
    names (``Smith-Jones``, ``O'Neil``), ``Mc`` prefixes (``McDonald``),
    lower-case particles (``van der Berg``), generational suffixes
    (``Jr.``, ``III``) and initials (``J. K. Rowling``). Placeholder values
    (``n/a``, ``unknown``, ``-``) and values with no letters become ``None``.

    Auto-detection is by column name only: it matches person-name columns
    such as ``fname``, ``lname``, ``mname``, ``first_name``, ``surname`` and
    ``full_name``, and only string columns. A bare ``name`` column is
    deliberately not matched, since it is often a company or product name.

    Attributes:
        preserve_mixed_case: If True (default), a name that already mixes
            upper and lower case (e.g. ``McDonald``) is only
            whitespace-normalized, never re-cased.
        extra_null_values: Additional placeholder strings (matched
            case-insensitively) to treat as missing, on top of
            ``DEFAULT_NULL_VALUES``.
    """

    DEFAULT_NULL_VALUES: ClassVar[frozenset[str]] = frozenset(
        {"n/a", "na", "null", "none", "unknown", "-", "--", "?", "nil", "tbc"}
    )
    PARTICLES: ClassVar[frozenset[str]] = frozenset(
        {"van", "von", "de", "der", "den", "di", "da", "del", "della", "du", "la", "le"}
    )
    SUFFIXES: ClassVar[dict[str, str]] = {
        "jr": "Jr",
        "sr": "Sr",
        "ii": "II",
        "iii": "III",
        "iv": "IV",
    }

    _SPACE_RE: ClassVar[re.Pattern[str]] = re.compile(r"\s+")
    _LETTER_RE: ClassVar[re.Pattern[str]] = re.compile(r"[^\W\d_]")
    _APOSTROPHE_RE: ClassVar[re.Pattern[str]] = re.compile(r"(['’])")
    # Short forms must stand alone (or be concatenated, e.g. "lnamefname") so
    # that "colname" or "filename" never match.
    _SHORT_NAME_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"(?:^|[^a-z])(?:[flm]name)+(?:$|[^a-z])"
    )
    _LONG_NAME_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"first_?name|last_?name|middle_?name|full_?name|given_?name|"
        r"family_?name|maiden_?name|forename|surname"
    )

    preserve_mixed_case: bool = True
    extra_null_values: tuple[str, ...] = ()

    _null_values: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Initialize base cleaner state and compile the null-value set."""
        super().__post_init__()
        self._null_values = self.DEFAULT_NULL_VALUES | {
            value.lower() for value in self.extra_null_values
        }

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore
        """Normalize ``v`` as a personal name.

        Args:
            v: The raw name.

        Returns:
            The normalized name, or None if ``v`` is a placeholder or
            contains no letters.
        """
        text = self._SPACE_RE.sub(" ", v).strip()

        if text.lower() in self._null_values or not self._LETTER_RE.search(text):
            return None

        if self.preserve_mixed_case and not (text.isupper() or text.islower()):
            return text

        return " ".join(
            self._format_word(word, index) for index, word in enumerate(text.split(" "))
        )

    def _format_word(self, word: str, index: int) -> str:
        """Re-case one space-separated word of a name."""
        lowered = word.lower()

        if index > 0 and lowered in self.PARTICLES:
            return lowered

        bare = lowered.rstrip(".")
        suffix = self.SUFFIXES.get(bare)
        if suffix is not None:
            return suffix + lowered[len(bare) :]

        return "-".join(self._format_part(part) for part in lowered.split("-"))

    def _format_part(self, part: str) -> str:
        """Re-case one hyphen-free piece, capitalizing around apostrophes."""
        pieces = self._APOSTROPHE_RE.split(part)
        return "".join(self._capitalize(piece) for piece in pieces)

    @staticmethod
    def _capitalize(piece: str) -> str:
        """Capitalize a lower-case piece, with the ``Mc`` prefix rule."""
        if len(piece) > 2 and piece.startswith("mc") and piece[2:].isalpha():
            return "Mc" + piece[2:].capitalize()
        return piece[:1].upper() + piece[1:]

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
