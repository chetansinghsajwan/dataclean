import re
import uuid
from enum import StrEnum
from typing import override

from dataclean.cleaners.base_cleaner import BaseCleaner
from dataclean.engine.dataframe import DataFrame, DataType


class UuidCleaner(BaseCleaner, frozen=True):
    class Format(StrEnum):
        STANDARD = "standard"  # Hyphenated: "123e4567-e89b-12d3-a456-426614174000"
        COMPACT = "compact"  # Raw hex: "123e4567e89b12d3a456426614174000"
        URN = "urn"  # Prefix URI: "urn:uuid:123e4567-e89b-12d3-a456-426614174000"

    out_format: Format = Format.STANDARD

    # Restrict to specific versions (e.g., {4, 7}). Set to None to accept any valid version.
    allowed_versions: set[int] | None = None

    @override
    def name(self) -> str:
        return "UuidCleaner"

    @override
    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]:
        return "str"

    @override
    def clean_value(self, v: str) -> str | None:
        # Base class contract guarantees v arrives stripped and non-empty
        normalized = v.lower().strip("'\"{}()[]")

        if normalized.startswith("urn:uuid:"):
            normalized = normalized[9:]

        # 1. Fast-Path Attempt: Native execution check
        try:
            uuid_obj = uuid.UUID(normalized)
        except ValueError:
            # 2. Resilient Fallback: Isolate pure hex tokens from messy text anomalies
            hex_only = "".join(re.findall(r"[0-9a-f]", normalized))
            if len(hex_only) != 32:
                return None
            try:
                uuid_obj = uuid.UUID(hex_only)
            except ValueError:
                return None

        # Allow only specific UUID versions if set
        if (
            self.allowed_versions is not None
            and uuid_obj.version not in self.allowed_versions
        ):
            return None

        # Standardized layout transformation output
        match self.out_format:
            case UuidCleaner.Format.STANDARD:
                return str(uuid_obj)
            case UuidCleaner.Format.COMPACT:
                return uuid_obj.hex
            case UuidCleaner.Format.URN:
                return uuid_obj.urn

        return None

    @override
    def get_data_type_confidence(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        if not cols:
            return 0.0

        col_name = cols[0].lower()
        # Heuristic 1: Explicit structural column name targeting
        if any(
            token in col_name for token in ("uuid", "guid", "pk_id", "session_token")
        ):
            return 1.0

        # Heuristic 2: Sample value structural layout validation
        # Fetches a small sample array from the dataframe to spot-check the text structure
        sample_values = (
            df.select(cols[0]).limit(5).to_pandas()[cols[0]].dropna().astype(str)
        )
        if sample_values.empty:
            return 0.0

        # Run a highly accurate regex check matching standard or compact layout patterns
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        match_count = sum(
            1
            for val in sample_values
            if uuid_pattern.match(str(val).strip("'\"{}()[] ").replace("urn:uuid:", ""))
        )

        # If at least half of the non-null samples match the layout, flag high structural confidence
        if match_count / len(sample_values) >= 0.5:
            return 0.9

        return 0.0
