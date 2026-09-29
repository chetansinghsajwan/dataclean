"""Cleaner for normalizing messy date/time strings into a canonical format."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum
from typing import override

from dataclean.engine import DataFrame
from dataclean.types import checked

from .cleaner import Cleaner


@checked
@dataclass
class DateTimeCleaner(Cleaner):
    """Parses messy date, time, or datetime strings and re-emits them canonically.

    Incoming values are matched, in order, against a fixed list of known
    structural formats (see ``_TRY_FORMATS``). The first format that parses
    successfully determines whether the value is treated as a date, a time,
    or a full datetime, and that parsed value is then rendered using
    ``out_format``.

    Attributes:
        out_format: The output layout to render the parsed value as.
    """

    class Format(StrEnum):
        """Output layouts supported for cleaned date/time values."""

        ISO_DATETIME = "iso_datetime"  # 2026-06-19T22:45:00
        ISO_DATE = "iso_date"  # 2026-06-19
        ISO_TIME = "iso_time"  # 22:45:00
        INDIAN_DATE = "indian_date"  # 19-06-2026

    out_format: Format = Format.ISO_DATETIME

    # A sequence of structural formats to test against incoming messy strings
    _TRY_FORMATS: tuple[str, ...] = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%H:%M:%S",
        "%I:%M %p",
    )

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore
        """Parse ``v`` against known date/time formats and render it as ``out_format``.

        Args:
            v: The raw date/time string to clean.

        Returns:
            The value rendered per ``out_format``, or None if ``v`` does not
            match any known format, or if the parsed value's kind (date, time,
            or datetime) is incompatible with the requested ``out_format``
            (e.g. requesting ``ISO_DATE`` for a bare time value).
        """

        # Implementation contract guarantee: v is a non-empty, stripped string
        parsed_obj: date | time | datetime | None = None

        for fmt in self._TRY_FORMATS:
            try:
                if fmt in ("%H:%M:%S", "%I:%M %p"):
                    parsed_obj = datetime.strptime(v, fmt).time()
                else:
                    parsed_obj = datetime.strptime(v, fmt)
                break
            except ValueError:
                continue

        if parsed_obj is None:
            return None

        # Build output structure based on chosen format rule
        match self.out_format:
            case DateTimeCleaner.Format.ISO_DATETIME:
                if isinstance(parsed_obj, time):
                    return datetime.combine(date.min, parsed_obj).isoformat()
                return parsed_obj.isoformat()

            case DateTimeCleaner.Format.ISO_DATE:
                if isinstance(parsed_obj, time):
                    return None
                return parsed_obj.date().isoformat()

            case DateTimeCleaner.Format.ISO_TIME:
                if isinstance(parsed_obj, time):
                    return parsed_obj.isoformat()
                return parsed_obj.time().isoformat()

            case DateTimeCleaner.Format.INDIAN_DATE:
                if isinstance(parsed_obj, time):
                    return None
                return parsed_obj.strftime("%d-%m-%Y")

        return None

    @override
    def match_score(self, df: DataFrame, cols: Iterable[str]) -> float:
        """Score confidence based on the column name looking date/time related.

        Args:
            df: The dataframe being inspected (unused; scoring here is
                name-based only).
            cols: Candidate column name(s); only the first is considered.

        Returns:
            1.0 if the column name contains a date/time-related token or
            ends with an "_at"/"At" suffix, otherwise 0.0.
        """
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0

        col_name = cols_tuple[0].lower()
        if (
            any(token in col_name for token in ("date", "time", "timestamp"))
            or col_name.lower().endswith("_at")
            or col_name.endswith("At")
        ):
            return 1.0

        return 0.0
