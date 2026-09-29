"""Cleaner for validating and re-formatting UUID strings."""

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import override

from dataclean.engine import DataFrame
from dataclean.types import checked

from .cleaner import Cleaner


@checked
@dataclass
class UuidCleaner(Cleaner):
    """Validates and re-formats UUID strings, tolerating common surface noise.

    Strips surrounding quoting/bracket characters and a leading
    "urn:uuid:" prefix, then attempts to parse the value as a UUID; if that
    fails, falls back to extracting exactly 32 hex characters from the
    remaining text. Optionally restricts accepted values to specific UUID
    versions.

    Attributes:
        out_format: The output layout to render valid UUIDs as.
        allowed_versions: If set, only UUIDs whose version is in this set
            are accepted; None accepts any valid version.
    """

    class Format(StrEnum):
        """Output layouts supported for cleaned UUID values."""

        STANDARD = "standard"  # Hyphenated: "123e4567-e89b-12d3-a456-426614174000"
        COMPACT = "compact"  # Raw hex: "123e4567e89b12d3a456426614174000"
        URN = "urn"  # Prefix URI: "urn:uuid:123e4567-e89b-12d3-a456-426614174000"

    out_format: Format = Format.STANDARD

    # Restrict to specific versions (e.g., {4, 7}). Set to None to accept any valid version.
    allowed_versions: set[int] | None = None

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore
        """Parse ``v`` as a UUID and render it in ``out_format``.

        Args:
            v: The raw string to clean.

        Returns:
            The UUID rendered per ``out_format``, or None if ``v`` cannot be
            parsed as a UUID (including via the 32-hex-character fallback),
            or if its version is excluded by ``allowed_versions``.
        """

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
    def match_score(self, df: DataFrame, cols: Iterable[str]) -> float:
        """Score confidence based on the column name looking UUID/GUID-related.

        Args:
            df: The dataframe being inspected (unused; scoring here is
                name-based only).
            cols: Candidate column name(s); only the first is considered.

        Returns:
            1.0 if the column name contains a UUID/GUID-related token,
            otherwise 0.0.
        """
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0

        col_name = cols_tuple[0]
        col_name_lower = col_name.lower()
        # Heuristic 1: Explicit structural column name targeting
        if any(
            token in col_name_lower
            for token in ("uuid", "guid", "pk_id", "session_token")
        ):
            return 1.0

        return 0.0
