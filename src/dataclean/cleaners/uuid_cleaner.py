"""Cleaner for validating and re-formatting UUID strings."""

import re
import unicodedata
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, override

from dataclean.engine import DataFrame
from dataclean.types import checked
from dataclean.utils import has_words

from .cleaner import Cleaner


@checked
@dataclass
class UuidCleaner(Cleaner):
    """Validates and re-formats UUID strings, tolerating common surface noise.

    Strips surrounding quoting/bracket characters and a leading
    "urn:uuid:" or "0x" prefix, then accepts the value only if it is a
    UUID in a recognizable shape: 32 hex digits, or the 8-4-4-4-12 groups
    joined by one repeated separator ("-", "_", "." or a space). Anything else
    becomes None. Optionally restricts accepted values to specific UUID
    versions.

    Attributes:
        out_format: The output layout to render valid UUIDs as.
        allowed_versions: If set, only UUIDs whose version is in this set
            are accepted; None accepts any valid version.
        allow_nil: If False, the nil UUID (all zeros) is treated as a
            placeholder and becomes None.
        allow_max: If False, the max UUID (all f) is treated as a
            placeholder and becomes None.
        extract_from_text: If True (the default), a single UUID is also
            pulled out of surrounding text, so ``id: <uuid>`` and
            ``<uuid>, extra`` are cleaned to the UUID. If the text holds
            more than one UUID the value becomes None, since the right one
            cannot be told. Set it to False to accept only a value that is
            nothing but a UUID.
    """

    class Format(StrEnum):
        """Output layouts supported for cleaned UUID values."""

        STANDARD = "standard"  # Hyphenated: "123e4567-e89b-12d3-a456-426614174000"
        COMPACT = "compact"  # Raw hex: "123e4567e89b12d3a456426614174000"
        URN = "urn"  # Prefix URI: "urn:uuid:123e4567-e89b-12d3-a456-426614174000"

    out_format: Format = Format.STANDARD

    # Restrict to specific versions (e.g., {4, 7}). Set to None to accept any valid version.
    allowed_versions: set[int] | None = None
    allow_nil: bool = False
    allow_max: bool = False
    extract_from_text: bool = True

    _SEPARATORS: ClassVar[str] = r"[-_. ]"
    _SHAPE_RE: ClassVar[re.Pattern] = re.compile(
        r"[0-9a-f]{32}"
        r"|[0-9a-f]{8}(?P<sep>[-_. ])[0-9a-f]{4}(?P=sep)[0-9a-f]{4}(?P=sep)"
        r"[0-9a-f]{4}(?P=sep)[0-9a-f]{12}"
    )
    _EMBEDDED_RE: ClassVar[re.Pattern] = re.compile(
        r"(?<![0-9a-f])(?:[0-9a-f]{32}"
        r"|[0-9a-f]{8}(?P<sep>[-_. ])[0-9a-f]{4}(?P=sep)[0-9a-f]{4}(?P=sep)"
        r"[0-9a-f]{4}(?P=sep)[0-9a-f]{12})(?![0-9a-f])"
    )

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore
        """Parse ``v`` as a UUID and render it in ``out_format``.

        Args:
            v: The raw string to clean.

        Returns:
            The UUID rendered per ``out_format``, or None if ``v`` cannot be
            in a recognized UUID shape (or the version is excluded),
            or if its version is excluded by ``allowed_versions``.
        """

        # Base class contract guarantees v arrives stripped and non-empty.
        # NFKC turns full-width digits into ASCII before the shape check.
        normalized = unicodedata.normalize("NFKC", v).lower().strip("'\"{}()[]")

        for prefix in ("urn:uuid:", "0x"):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :]
                break

        match = self._SHAPE_RE.fullmatch(normalized)
        if match is None and self.extract_from_text:
            # Decision: text extraction is on by default, and a value with two
            # or more UUIDs gives None since the right one cannot be told.
            found = [m.group(0) for m in self._EMBEDDED_RE.finditer(normalized)]
            if len(found) != 1:
                return None
            match = self._SHAPE_RE.fullmatch(found[0])
        if match is None:
            return None

        uuid_obj = uuid.UUID(re.sub(self._SEPARATORS, "", match.group(0)))

        if (uuid_obj == uuid.UUID(int=0) and not self.allow_nil) or (
            uuid_obj == uuid.UUID(int=(1 << 128) - 1) and not self.allow_max
        ):
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
    def match_score(
        self, df: DataFrame, cols: Iterable[str], words: tuple[str, ...]
    ) -> float:
        """Score confidence based on the column name looking UUID/GUID-related.

        Args:
            df: The dataframe being inspected (unused; scoring here is
                name-based only).
            cols: Candidate column name(s); only the first is considered.
        words: The lowercase words of the column name, split with the same aliases for every cleaner.

        Returns:
            1.0 if the column name contains a UUID/GUID-related token,
            otherwise 0.0.
        """
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0

        # Heuristic 1: Explicit structural column name targeting
        if any(
            has_words(words, hint)
            for hint in ("uuid", "guid", "pk_id", "session_token")
        ):
            return 1.0

        return 0.0
