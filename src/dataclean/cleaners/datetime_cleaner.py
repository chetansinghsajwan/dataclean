from datetime import date, datetime, time
from enum import StrEnum
from typing import override

from dataclean.cleaners.base_cleaner import BaseCleaner
from dataclean.engine.dataframe import DataFrame, DataType


class DateTimeCleaner(BaseCleaner, frozen=True):
    class Format(StrEnum):
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
    def name(self) -> str:
        return "DateTimeCleaner"

    @override
    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]:
        return "str"

    @override
    def clean_value(self, v: str) -> str | None:
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
    def get_data_type_confidence(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        if not cols:
            return 0.0

        col_name = cols[0].lower()
        if (
            any(token in col_name for token in ("date", "time", "timestamp"))
            or col_name.lower().endswith("_at")
            or col_name.endswith("At")
        ):
            return 1.0

        return 0.0
