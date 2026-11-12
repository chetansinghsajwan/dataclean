"""Cleaner for normalizing messy numeric strings into ints or floats."""

import math
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum
from typing import ClassVar, override

from dataclean.engine import DataFrame, DataReader, DataType
from dataclean.types import checked

from .cleaner import Cleaner


@checked
@dataclass
class NumericCleaner(Cleaner):
    """Extracts a numeric value from a messy string and normalizes its output.

    Reads thousands and decimal separators in the common styles (``1,234.56``,
    ``1.234,56``, ``1 234,56``, Indian ``1,23,456``), strips currency markers
    and ``%``, treats brackets as a negative number, and reads a trailing
    "k"/"m"/"b"/"t" as a scale unless ``parse_suffixes`` is off. Anything else
    around the digits (other letters, a stray ``/``, groups that are not
    thousands) is not a number and gives None, so it is never turned into a
    wrong one. Parsing is exact (``Decimal``), the result is then optionally
    rounded and rendered as an int or float string.

    Identifier-like columns (``contactid``, ``postcode``, values with leading
    zeros, long digit strings, whole numbers that are all different) are not
    quantities, so ``match_score`` leaves them to nobody.

    Attributes:
        out_format: Whether to cast the cleaned value to ``int`` or
            ``float``. ``int`` gives None outside the 64-bit range.
        precision: Number of decimal places to round to (half-up), or None
            to skip rounding. Decision: the default of 3 is accepted as is;
            use 2 for strict financial limits.
        parse_suffixes: If True (the default), interpret a trailing
            "k"/"m"/"b"/"t" as a metric/financial scale suffix (thousand/
            million/billion/trillion) and multiply accordingly. If False, a
            value with such a suffix is not a number and gives None.
    """

    class Format(StrEnum):
        """Output numeric type for cleaned values."""

        INT = "int"  # Casts the cleaned value to a strict Python integer
        FLOAT = "float"  # Casts the cleaned value to a standard Python float

    out_format: Format = Format.FLOAT
    precision: int | None = 3  # e.g., Set to 2 for strict financial limits
    parse_suffixes: bool = True  # Set to False to reject 'K', 'M', 'B', 'T' values

    _SUFFIXES: ClassVar[dict[str, Decimal]] = {
        "k": Decimal(10) ** 3,
        "m": Decimal(10) ** 6,
        "b": Decimal(10) ** 9,
        "t": Decimal(10) ** 12,
    }

    # "rs." is matched with its dot so the dot is not read as a decimal point.
    _CURRENCY_RE: ClassVar[re.Pattern] = re.compile(
        r"(?<![a-z])(?:rs\.?|inr|usd|eur|gbp)(?![a-z])|[$₹£€¥]"
    )
    _NUMBER_RE: ClassVar[re.Pattern] = re.compile(
        r"(?P<mantissa>(?:\d|[.,]\d)[\d.,' _]*?)(?:e(?P<exp>[+-]?\d+))?"
    )
    _MAX_EXPONENT: ClassVar[int] = 400
    _INT64_MIN: ClassVar[int] = -(2**63)
    _INT64_MAX: ClassVar[int] = 2**63 - 1

    # Column-name tokens. Short ones must be a whole word ("age" is in "page").
    _QUANTITY_SUBSTRINGS: ClassVar[tuple[str, ...]] = (
        "amount",
        "price",
        "count",
        "quantity",
        "revenue",
        "total",
        "limit",
        "balance",
        "salary",
        "weight",
        "height",
    )
    _QUANTITY_WORDS: ClassVar[frozenset[str]] = frozenset(
        {"fee", "cost", "qty", "age", "rate", "score"}
    )
    _ID_RE: ClassVar[re.Pattern] = re.compile(
        r"(?:^|[^a-z0-9])(?:id|guid|uuid|key|code|pin|zip|postcode|pincode)$"
        r"|(?<=[a-z])(?:id|guid|uuid|code|postcode|pincode)$"
    )
    _NOT_ID_WORDS: ClassVar[tuple[str, ...]] = ("paid", "valid", "void", "humid")
    _NULL_LIKE: ClassVar[frozenset[str]] = frozenset(
        {
            "",
            "null",
            "none",
            "nan",
            "n/a",
            "na",
            "-",
            "undefined",
            "''",
            '""',
            "inf",
            "+inf",
            "-inf",
            "infinity",
            "+infinity",
            "-infinity",
        }
    )
    _LONG_DIGITS: ClassVar[int] = 12
    _UNIQUE_MIN_ROWS: ClassVar[int] = 20
    _UNIQUE_RATIO: ClassVar[float] = 0.95
    _SAMPLE_LIMIT: ClassVar[int] = 100

    @override
    def _outputs(self) -> Cleaner.OutputSchema:
        """Return the output schema with dtype set per ``out_format``.

        Decision: floats are ``DOUBLE`` and integers are ``LONG`` (64-bit),
        because 32-bit floats lost digits and Spark ``INT`` is only 32-bit.
        """
        return Cleaner.OutputSchema(
            cols=(
                Cleaner.OutputSchema.Column(
                    dtype=DataType.LONG
                    if self.out_format == NumericCleaner.Format.INT
                    else DataType.DOUBLE
                ),
            )
        )

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore
        """Extract and normalize a numeric value from ``v``.

        Args:
            v: The raw string to parse.

        Returns:
            The cleaned numeric value rendered as a string (per
            ``out_format`` and ``precision``), or None if ``v`` is not a
            number, the value is non-finite or out of range for the output
            type, or it has too many significant digits to be rounded to
            ``precision``.
        """

        # Base implementation pipeline guarantees that v arrives non-empty and stripped
        value = self._parse(v)
        if value is None:
            return None

        if self.precision is not None:
            try:
                value = value.quantize(
                    Decimal(10) ** -self.precision, rounding=ROUND_HALF_UP
                )
            except InvalidOperation:
                # Too many significant digits for the decimal context
                return None

        if value.is_zero():
            value = Decimal(0)

        match self.out_format:
            case NumericCleaner.Format.INT:
                whole = int(value)
                if not self._INT64_MIN <= whole <= self._INT64_MAX:
                    return None
                return str(whole)
            case NumericCleaner.Format.FLOAT:
                as_float = float(value)
                return str(as_float) if math.isfinite(as_float) else None

        return None

    def _parse(self, v: str) -> Decimal | None:
        """Read ``v`` as an exact decimal, or None if it is not a number."""
        text = self._to_ascii_digits(v).lower()
        text = self._CURRENCY_RE.sub("", text).strip()
        if text.endswith("%"):
            text = text[:-1].strip()

        negative = False
        if len(text) > 2 and text[0] == "(" and text[-1] == ")":
            negative, text = True, text[1:-1].strip()
        if text and text[0] in "+-":
            negative ^= text[0] == "-"
            text = text[1:].strip()

        multiplier = None
        if self.parse_suffixes and len(text) > 1 and text[-1] in self._SUFFIXES:
            multiplier = self._SUFFIXES[text[-1]]
            text = text[:-1].rstrip()

        match = self._NUMBER_RE.fullmatch(text)
        if match is None:
            return None

        plain = self._plain_mantissa(match["mantissa"])
        if plain is None:
            return None

        exponent = match["exp"] or "0"
        if abs(int(exponent)) > self._MAX_EXPONENT:
            return None

        value = Decimal(f"{plain}e{exponent}")
        if multiplier is not None:
            value = value * multiplier
        return value.copy_negate() if negative else value

    @staticmethod
    def _to_ascii_digits(v: str) -> str:
        """Fold full-width and other-script digits and separators to ASCII."""
        v = unicodedata.normalize("NFKC", v)
        v = v.replace("٫", ".").replace("٬", ",")
        return "".join(
            str(unicodedata.decimal(c)) if c.isdecimal() else c for c in v
        ).replace(" ", " ")

    @classmethod
    def _plain_mantissa(cls, mantissa: str) -> str | None:
        """Turn ``1.234,56`` style text into plain ``1234.56``, or None.

        The decimal separator is the last of "." and "," when both appear. A
        lone "," is a decimal unless exactly 3 digits follow it. A lone "." is
        a decimal unless it is a valid thousands separator used several times;
        repeated dots that are not thousands are a typo for one decimal point.
        """
        mantissa = mantissa.strip()
        last_dot, last_comma = mantissa.rfind("."), mantissa.rfind(",")
        decimal: str | None = None

        if last_dot >= 0 and last_comma >= 0:
            decimal = "." if last_dot > last_comma else ","
            if mantissa.count(decimal) != 1:
                return None
        elif last_comma >= 0:
            if mantissa.count(",") == 1:
                before, after = mantissa.split(",")
                if len(after) != 3 or before.replace(" ", "") == "0":
                    decimal = ","
        elif last_dot >= 0:
            if mantissa.count(".") == 1 or cls._thousands_digits(mantissa) is None:
                decimal = "."

        if decimal is None:
            return cls._thousands_digits(mantissa)

        whole, fraction = mantissa.split(decimal, 1)
        if decimal == ".":
            fraction = fraction.replace(".", "")  # typo recovery for "1..5"
        if fraction and not fraction.isdigit():
            return None

        digits = cls._thousands_digits(whole) if whole.strip() else "0"
        if digits is None:
            return None
        return f"{digits}.{fraction}" if fraction else digits

    @staticmethod
    def _thousands_digits(text: str) -> str | None:
        """Join digit groups split by one thousands mark, or None if invalid.

        Accepts groups of 3 (``1,234,567``) and the Indian style
        (``12,34,567``).
        """
        text = text.strip()
        marks = {c for c in text if not c.isdigit()}
        if not marks:
            return text or None
        if len(marks) > 1:
            return None

        groups = text.split(marks.pop())
        if not all(g.isdigit() for g in groups):
            return None
        first, rest = groups[0], groups[1:]
        standard = len(first) <= 3 and all(len(g) == 3 for g in rest)
        indian = (
            len(first) <= 2
            and all(len(g) == 2 for g in rest[:-1])
            and len(rest[-1]) == 3
        )
        return "".join(groups) if standard or indian else None

    @override
    def match_score(self, df: DataFrame, cols: Iterable[str]) -> float:
        """Score confidence via a column-name heuristic plus a data-sampling pass.

        Identifier-like columns score 0.0. Otherwise combines a 30% weight
        for the column name hinting at a quantity (amount, price, limit,
        etc.) with a 70% weight for the fraction of up to 100 sampled values
        that clean via ``clean_row``. Missing and placeholder values (None,
        NaN, blanks, "null", "n/a", infinity) are left out of the sample.

        Args:
            df: The dataframe to sample values from.
            cols: Candidate column name(s); only the first is considered.

        Returns:
            A confidence score between 0.0 and 1.0.
        """
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0

        col_name = cols_tuple[0].lower()
        if self._looks_like_id_name(col_name):
            return 0.0

        samples: list[str] = []

        def collect(val: str | bool | int | float | None) -> None:
            """Keep one more non-missing value, up to the sample limit."""
            if len(samples) < self._SAMPLE_LIMIT and not self._is_null_like(val):
                samples.append(str(val).strip())

        df.read_cols([DataReader(fn=collect, cols=(cols_tuple[0],))])

        if not samples:
            return 0.0
        if self._looks_like_id_values(samples):
            return 0.0

        confidence = 0.3 if self._has_quantity_hint(col_name) else 0.0
        valid = sum(self.clean_row(s) is not None for s in samples)
        confidence += valid / len(samples) * 0.7
        return min(confidence, 1.0)

    @classmethod
    def _is_null_like(cls, val: object) -> bool:
        """Return whether ``val`` is missing or a placeholder for "no value"."""
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return True
        return str(val).strip().lower() in cls._NULL_LIKE

    @classmethod
    def _has_quantity_hint(cls, col_name: str) -> bool:
        """Return whether the column name hints at a quantity."""
        if any(token in col_name for token in cls._QUANTITY_SUBSTRINGS):
            return True
        return any(w in cls._QUANTITY_WORDS for w in re.split(r"[^a-z0-9]+", col_name))

    @classmethod
    def _looks_like_id_name(cls, col_name: str) -> bool:
        """Return whether the column name says identifier or code.

        Decision: a copy number after a separator ("contacttypeid_2",
        "user id 3") is ignored, since a second set of id columns is still ids
        and must not be cleaned as a number.
        """
        col_name = re.sub(r"[^a-z0-9]\d+$", "", col_name)
        if col_name.endswith(cls._NOT_ID_WORDS):
            return False
        return cls._ID_RE.search(col_name) is not None

    @classmethod
    def _looks_like_id_values(cls, samples: list[str]) -> bool:
        """Return whether the values look like identifiers, not quantities.

        Identifiers have leading zeros, are long digit strings, or are whole
        numbers that are almost all different.
        """
        if any(re.fullmatch(r"0\d+", s) for s in samples):
            return True
        if any(re.fullmatch(rf"\d{{{cls._LONG_DIGITS},}}", s) for s in samples):
            return True
        if len(samples) >= cls._UNIQUE_MIN_ROWS and all(s.isdigit() for s in samples):
            return len(set(samples)) / len(samples) >= cls._UNIQUE_RATIO
        return False
