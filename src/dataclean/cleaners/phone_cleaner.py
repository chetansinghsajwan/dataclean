"""Cleaner for parsing and normalizing phone numbers."""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import override

import phonenumbers

from dataclean.engine import DataFrame
from dataclean.types import checked

from .cleaner import Cleaner
from .country_cleaner import CountryCleaner


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
    self-contained, it cannot be judged valid or invalid, so it is returned
    unchanged (stripped) rather than being discarded as ``None``.
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
            v: The raw phone number string to clean, or None.
            country: Optional country of the number (name or ISO code); its
                region is tried before ``default_regions``.

        Returns:
            The cleaned number rendered per ``out_format``; None if ``v`` is
            None or is not a valid number under any known region; or ``v``
            unchanged (stripped) if no region is known and it is not
            self-contained, since validity cannot be determined.
        """

        if v is None:
            return None

        normalized = v.strip()

        if re.match(r"^\d+(\.\d+)?([eE][+-]?\d+)$", normalized):
            try:
                normalized = str(int(float(normalized)))
            except ValueError:
                pass

        regions = self._regions_for(country)
        if not regions and not normalized.startswith("+"):
            # No region to validate against: keep the value rather than
            # silently discarding a number that may well be valid.
            return normalized

        # Run at least once so self-contained formats (+91...) parse with no region.
        regions_to_try = regions if regions else (None,)

        for region in regions_to_try:
            try:
                parsed_num = phonenumbers.parse(normalized, region)

                if phonenumbers.is_valid_number(parsed_num):
                    match self.out_format:
                        case PhoneCleaner.Format.E164:
                            return phonenumbers.format_number(
                                parsed_num, phonenumbers.PhoneNumberFormat.E164
                            )
                        case PhoneCleaner.Format.INTERNATIONAL:
                            return phonenumbers.format_number(
                                parsed_num, phonenumbers.PhoneNumberFormat.INTERNATIONAL
                            )
                        case PhoneCleaner.Format.NATIONAL:
                            return phonenumbers.format_number(
                                parsed_num, phonenumbers.PhoneNumberFormat.NATIONAL
                            )
                        case PhoneCleaner.Format.RAW_DIGITS:
                            e164 = phonenumbers.format_number(
                                parsed_num, phonenumbers.PhoneNumberFormat.E164
                            )
                            return e164.replace("+", "")

            except phonenumbers.NumberParseException:
                continue

        return None

    def _regions_for(self, country: str | None) -> tuple[str, ...]:
        """Return the regions to try: the row's country first, then ``default_regions``."""
        if country is None or not country.strip():
            return self.default_regions
        region = self._country_cleaner.clean_row(country.strip())
        if region is None:
            return self.default_regions
        return (region, *(r for r in self.default_regions if r != region))

    @override
    def match_score(self, df: DataFrame, cols: Iterable[str]) -> float:
        """Score confidence based on the column name looking phone-related.

        Args:
            df: The dataframe being inspected (unused; scoring here is
                name-based only).
            cols: Candidate column name(s); only the first is considered.

        Returns:
            1.0 if the column name contains a phone-related token,
            otherwise 0.0.
        """
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0

        col_name = cols_tuple[0].lower()
        if any(
            token in col_name
            for token in ("phone", "tel", "mobile", "fax", "contact_no")
        ):
            return 1.0

        return 0.0
