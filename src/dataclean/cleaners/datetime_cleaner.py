"""Cleaner for normalizing messy date/time strings into a canonical format."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone, tzinfo
from enum import StrEnum
from typing import ClassVar, override
from zoneinfo import ZoneInfo

from dataclean.engine import DataFrame, DataType
from dataclean.types import checked

from .cleaner import Cleaner


@checked
@dataclass
class DateTimeCleaner(Cleaner):
    """Parses messy date, time, or datetime strings and re-emits them canonically.

    A trailing time (with an optional AM/PM and timezone) is split off first,
    and the rest is read as a date: ISO (`2026-06-19`, `2026/06/19`), compact
    (`20260619`), numeric day and month (`19/06/2026`, `19-06-2026`,
    `19.06.2026`) or with a month name (`19 Jun 2026`, `June 19, 2026`). A
    value with only a time is read as a time of day.

    Attributes:
        out_format: The output layout to render the parsed value as.
        day_first: If True, `03/04/2026` is 3 April and `03/14/2026` is
            rejected. If False it is 4 March and `19/06/2026` is rejected.
            Values are never guessed in both orders.
        default_timezone: IANA timezone name. A value with an offset or `Z` is
            converted to this timezone and written with its offset. A value
            without one is taken to be in this timezone and left as written.
        null_placeholder_dates: If True, dates databases use for "no date"
            (`0001-01-01`, `1900-01-01`, `2099-12-31`, `9999-12-31`) become
            None.
        min_date: Dates before this become None. None keeps every date.
        max_date: Dates after this become None. None keeps every date.
    """

    class Format(StrEnum):
        """Output layouts supported for cleaned date/time values."""

        AUTO = "auto"  # 2026-06-19, 2026-06-19T22:45:00 or 22:45:00, as the input
        ISO_DATETIME = "iso_datetime"  # 2026-06-19T22:45:00
        ISO_DATE = "iso_date"  # 2026-06-19
        ISO_TIME = "iso_time"  # 22:45:00
        INDIAN_DATE = "indian_date"  # 19-06-2026

    out_format: Format = Format.AUTO
    day_first: bool = True
    default_timezone: str = "UTC"
    null_placeholder_dates: bool = True
    min_date: date | None = None
    max_date: date | None = None

    _PLACEHOLDER_DATES: ClassVar[frozenset[date]] = frozenset(
        {date(1, 1, 1), date(1900, 1, 1), date(2099, 12, 31), date(9999, 12, 31)}
    )
    # Time of day at the end of the value, with optional AM/PM and timezone.
    _TIME_RE: ClassVar[re.Pattern] = re.compile(
        r"(?:^|[T\s,])"
        r"(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2})(?:[.,](?P<f>\d{1,6})\d*)?)?"
        r"\s*(?P<ampm>[AaPp][Mm])?"
        r"\s*(?P<tz>[Zz]|UTC|GMT|[+-]\d{2}(?::?\d{2})?)?$"
    )
    _NUMERIC_DATE_RE: ClassVar[re.Pattern] = re.compile(
        r"(\d{1,4})[-/.](\d{1,2})[-/.](\d{1,4})"
    )
    _COMPACT_DATE_RE: ClassVar[re.Pattern] = re.compile(r"\d{8}")
    _NAMED_DATE_FORMATS: ClassVar[tuple[str, ...]] = (
        "%d %b %Y",
        "%d %B %Y",
        "%b %d %Y",
        "%B %d %Y",
        "%d-%b-%Y",
        "%d-%B-%Y",
    )

    _tz: tzinfo | None = None

    def __post_init__(self) -> None:
        """Initialize base cleaner state and load the default timezone."""
        super().__post_init__()
        self._tz = ZoneInfo(self.default_timezone)

    @staticmethod
    def _parse_offset(token: str) -> tzinfo:
        """Turn `Z`, `UTC`, `+05:30` or `+0530` into a fixed-offset timezone."""
        if token[0] not in "+-":
            return UTC
        sign = -1 if token[0] == "-" else 1
        digits = token[1:].replace(":", "")
        delta = timedelta(hours=int(digits[:2]), minutes=int(digits[2:] or 0))
        return timezone(sign * delta)

    def _parse_date(self, text: str) -> date | None:
        """Read the date part of a value, or return None if it is not a date."""
        text = " ".join(text.replace(",", " ").split())
        try:
            if self._COMPACT_DATE_RE.fullmatch(text):
                return datetime.strptime(text, "%Y%m%d").date()
            numeric = self._NUMERIC_DATE_RE.fullmatch(text)
            if numeric:
                first, second, third = numeric.groups()
                if len(first) == 4 and len(third) <= 2:
                    return date(int(first), int(second), int(third))
                if len(third) == 4 and len(first) <= 2:
                    day, month = (first, second) if self.day_first else (second, first)
                    return date(int(third), int(month), int(day))
                return None
            for fmt in self._NAMED_DATE_FORMATS:
                try:
                    return datetime.strptime(text, fmt).date()
                except ValueError:
                    continue
        except ValueError:
            return None
        return None

    def _date_allowed(self, day: date) -> bool:
        """Apply the placeholder and range rules to a parsed date."""
        if self.null_placeholder_dates and day in self._PLACEHOLDER_DATES:
            return False
        if self.min_date is not None and day < self.min_date:
            return False
        return self.max_date is None or day <= self.max_date

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore
        """Parse ``v`` as a date, time or datetime and render it as ``out_format``.

        Args:
            v: The raw date/time string to clean.

        Returns:
            The value rendered per ``out_format``, or None if ``v`` is not a
            recognizable date or time, is a placeholder or out-of-range date,
            or its kind (date, time or datetime) cannot be shown in the
            requested ``out_format`` (e.g. ``ISO_DATE`` for a bare time).
        """

        # Implementation contract guarantee: v is a non-empty, stripped string
        clock: time | None = None
        offset: tzinfo | None = None
        date_text = v

        found = self._TIME_RE.search(v)
        if found:
            hour = int(found["h"])
            if found["ampm"]:
                if not 1 <= hour <= 12:
                    return None
                hour = hour % 12 + (12 if found["ampm"].lower() == "pm" else 0)
            micro = int(found["f"].ljust(6, "0")) if found["f"] else 0
            try:
                clock = time(hour, int(found["m"]), int(found["s"] or 0), micro)
                offset = self._parse_offset(found["tz"]) if found["tz"] else None
            except ValueError:
                return None
            date_text = v[: found.start()]

        day: date | None = None
        if date_text.strip(" T,"):
            day = self._parse_date(date_text.strip(" T,"))
            if day is None or not self._date_allowed(day):
                return None

        if day is None:
            # Time only: a timezone cannot be converted without a date.
            if clock is None or offset is not None:
                return None
            return self._render(None, clock)

        if clock is None:
            return self._render(day, None)

        moment = datetime.combine(day, clock, tzinfo=offset)
        if offset is not None:
            try:
                moment = moment.astimezone(self._tz)
            except (OverflowError, ValueError):
                return None
        return self._render(moment, clock)

    def _render(self, value: date | datetime | None, clock: time | None) -> str | None:
        """Write a parsed value in ``out_format``, or None if it cannot be shown."""
        match self.out_format:
            case DateTimeCleaner.Format.AUTO:
                if value is None:
                    return clock.isoformat() if clock else None
                return value.isoformat()

            case DateTimeCleaner.Format.ISO_DATETIME:
                if value is None and clock is not None:
                    return datetime.combine(date.min, clock).isoformat()
                if value is None:
                    return None
                if isinstance(value, datetime):
                    return value.isoformat()
                return datetime.combine(value, time()).isoformat()

            case DateTimeCleaner.Format.ISO_DATE:
                if value is None:
                    return None
                return (
                    value.date() if isinstance(value, datetime) else value
                ).isoformat()

            case DateTimeCleaner.Format.ISO_TIME:
                if value is None:
                    return clock.isoformat() if clock else None
                if isinstance(value, datetime):
                    return value.time().isoformat()
                return time().isoformat()

            case DateTimeCleaner.Format.INDIAN_DATE:
                if value is None:
                    return None
                return value.strftime("%d-%m-%Y")

        return None

    @override
    def match_score(self, df: DataFrame, cols: Iterable[str]) -> float:
        """Score confidence based on the column name looking date/time related.

        Columns that already have a date, datetime or time type are never
        matched: there is nothing to parse, and cleaning them would turn the
        typed values into strings.

        Args:
            df: The dataframe being inspected; used only to skip columns that
                are already temporal.
            cols: Candidate column name(s); only the first is considered.

        Returns:
            1.0 if the column name contains a date/time-related token or
            ends with an "_at"/"At" suffix (and the column is not already
            temporal), otherwise 0.0.
        """
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0

        if dict(df.cols()).get(cols_tuple[0]) in (
            DataType.DATE,
            DataType.DATETIME,
            DataType.TIME,
        ):
            return 0.0

        col_name = cols_tuple[0].lower()
        if (
            any(token in col_name for token in ("date", "time", "timestamp"))
            or col_name.lower().endswith("_at")
            or col_name.endswith("At")
        ):
            return 1.0

        return 0.0
