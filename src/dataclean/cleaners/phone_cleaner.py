"""Cleaner for parsing and normalizing phone numbers."""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import override

import phonenumbers

from dataclean.engine import DataFrame
from dataclean.types import checked
from dataclean.utils import has_words, plain_text

from .cleaner import Cleaner
from .country_cleaner import CountryCleaner

# A leading label such as "tel:" or "mobile:".
_LABEL = re.compile(r"^[A-Za-z][A-Za-z .]*:\s*")

# A trailing word in brackets such as "(Mobile)" or "(fax)". Brackets with
# digits, as in "+44 (0)20", are part of the number and are kept.
_TRAILING_NOTE = re.compile(r"\s*\([^\d()]*[A-Za-z][^\d()]*\)\s*$")

# Separators that put several numbers in one cell.
_NUMBER_SEPARATORS = re.compile(r"\s*(?:[/;|,&]|\bor\b)\s*", re.IGNORECASE)

# A word of letters joined to the digits, as in "1-800-FLOWERS".
_VANITY = re.compile(r"[-\d)][A-Za-z]{3,}")

# E.164 numbers have at most 15 digits.
_MAX_DIGITS = 15


def _to_ascii_digits(value: str) -> str:
    """Replace digits of other scripts, such as Arabic-Indic, with 0-9."""
    return "".join(
        str(unicodedata.decimal(char)) if char.isdecimal() else char for char in value
    )


@checked
@dataclass
class PhoneCleaner(Cleaner):
    """Parses messy phone number strings and renders them in a canonical format.

    Delegates parsing and validation to the ``phonenumbers`` library. A
    number is accepted only if ``phonenumbers`` considers it valid for one
    of the tried regions. Self-contained international formats (e.g.
    "+91...") are also accepted even when ``default_regions`` is empty.

    Attributes:
        out_format: The output layout to render valid numbers as.
        default_regions: ISO region codes (e.g. "IN", "US") to try, in
            order, when the input doesn't carry its own country code. If
            empty, parsing is attempted with no default region, relying on
            the number being self-contained (e.g. E.164 with a "+" prefix).

    The row's ``country`` input (when supplied, e.g. from a country column
    in the same table) is resolved to a region and tried before
    ``default_regions``. If no region is known at all and the number is not
    self-contained, it cannot be judged valid or invalid, so a value with
    digits is returned unchanged (stripped) and one without is ``None``.

    Labels ("tel:", "mobile:"), trailing notes ("(fax)"), the "00"
    international prefix and non-ASCII digits are handled before parsing. A
    cell holding several numbers, split by ``/``, ``;``, ``|``, ``,``, ``&``
    or ``or``, gives the first one that cleans.
    """

    class Format(StrEnum):
        """Output layouts supported for cleaned phone numbers."""

        E164 = "e164"
        INTERNATIONAL = "international"
        NATIONAL = "national"
        RAW_DIGITS = "raw_digits"

    out_format: Format = Format.E164
    default_regions: tuple[str, ...] = ()
    _country_cleaner: CountryCleaner = field(
        init=False,
        repr=False,
        compare=False,
        default_factory=lambda: CountryCleaner(out_format=CountryCleaner.Format.ALPHA2),
    )

    @override
    def _outputs(self) -> Cleaner.OutputSchema:
        """Return the output schema, tagging the single output column with the "phone" role."""
        return Cleaner.OutputSchema(
            cols=(Cleaner.OutputSchema.Column(roles=("phone",)),)
        )

    @override
    def clean_row(self, v: str | None, country: str | None = None) -> str | None:  # type: ignore
        """Parse ``v`` as a phone number and render it in ``out_format``.

        Tries each region in ``default_regions`` (or no region, if empty)
        until ``phonenumbers`` parses ``v`` into a valid number.

        Args:
            v: The raw phone number string to clean, or None. HTML tags and
                emoji are removed first.
            country: Optional country of the number (name or ISO code); its
                region is tried before ``default_regions``.

        Returns:
            The cleaned number rendered per ``out_format``; None if ``v`` is
            None or is not a valid number under any known region; or ``v``
            unchanged (stripped) if no region is known and it is not
            self-contained, since validity cannot be determined, but only if
            it has a digit.
        """

        if v is None:
            return None
        v = plain_text(v)

        # A cell may hold several numbers: the first one that cleans wins.
        for part in _NUMBER_SEPARATORS.split(v):
            cleaned = self._clean_number(part, country)
            if cleaned is not None:
                return cleaned
        return None

    def _clean_number(self, v: str, country: str | None) -> str | None:
        """Clean a single number, as ``clean_row`` does for each part of a cell."""
        normalized = self._strip_noise(v)

        if re.match(r"^\d+(\.\d+)?([eE][+-]?\d+)$", normalized):
            try:
                normalized = str(int(float(normalized)))
            except ValueError:
                pass

        # Vanity numbers such as "1-800-FLOWERS" are not read as digits, since
        # the parser would turn the letters into a number of its own.
        if _VANITY.search(normalized):
            return None

        regions = self._regions_for(country)
        if not regions and not normalized.startswith("+"):
            # No region to validate against: keep a value that could be a
            # number rather than discarding one that may well be valid, and drop
            # one with no digits ("abc", "n/a") or too many to be a number.
            digits = sum(c.isdigit() for c in normalized)
            return normalized if 0 < digits <= _MAX_DIGITS else None

        # Run at least once so self-contained formats (+91...) parse with no region.
        regions_to_try = regions if regions else (None,)

        for region in regions_to_try:
            try:
                parsed_num = phonenumbers.parse(normalized, region)
            except phonenumbers.NumberParseException:
                continue
            if phonenumbers.is_valid_number(parsed_num):
                # Decision: a "+" number must write its country code in one
                # piece. "+22 (521) 234-56789" is read by the parser as "+225",
                # a guess across a separator, so it is rejected, not repaired.
                if normalized.startswith("+") and not re.match(
                    rf"\+\s*{parsed_num.country_code}", normalized
                ):
                    return None
                return self._render(parsed_num)

        return None

    def _strip_noise(self, value: str) -> str:
        """Strip labels, trailing notes and non-ASCII digits around a number.

        Turns "tel:+44 20 7946 0958", "+36 209 457 414 (Mobile)" and
        "00 44 20 7946 0958" into forms the parser accepts, and Arabic-Indic
        digits into 0-9.
        """
        cleaned = _to_ascii_digits(value.strip())
        cleaned = _LABEL.sub("", cleaned)
        cleaned = _TRAILING_NOTE.sub("", cleaned).strip()
        # "00" is the international dialing prefix in most countries.
        return re.sub(r"^00\s*(?=\d)", "+", cleaned)

    def _render(self, number: phonenumbers.PhoneNumber) -> str:
        """Render a valid number in ``out_format``."""
        match self.out_format:
            case PhoneCleaner.Format.E164:
                return phonenumbers.format_number(
                    number, phonenumbers.PhoneNumberFormat.E164
                )
            case PhoneCleaner.Format.INTERNATIONAL:
                return phonenumbers.format_number(
                    number, phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
            case PhoneCleaner.Format.NATIONAL:
                return phonenumbers.format_number(
                    number, phonenumbers.PhoneNumberFormat.NATIONAL
                )
            case PhoneCleaner.Format.RAW_DIGITS:
                return phonenumbers.format_number(
                    number, phonenumbers.PhoneNumberFormat.E164
                ).replace("+", "")

    def _regions_for(self, country: str | None) -> tuple[str, ...]:
        """Return the regions to try: the row's country first, then ``default_regions``."""
        if country is None or not country.strip():
            return self.default_regions
        region = self._country_cleaner.clean_row(country.strip())
        if region is None:
            return self.default_regions
        return (region, *(r for r in self.default_regions if r != region))

    @override
    def match_score(
        self, df: DataFrame, cols: Iterable[str], words: tuple[str, ...]
    ) -> float:
        """Score confidence based on the column name looking phone-related.

        Args:
            df: The dataframe being inspected (unused; scoring here is
                name-based only).
            cols: Candidate column name(s); only the first is considered.
        words: The lowercase words of the column name, split with the same aliases for every cleaner.

        Returns:
            1.0 if the column name has a phone-related word,
            otherwise 0.0.
        """
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0

        if any(
            has_words(words, hint)
            for hint in ("phone", "tel", "telephone", "mobile", "fax", "contact_no")
        ):
            return 1.0

        return 0.0
