"""Address cleaner for handling multi-column address data."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import override

from dataclean.engine import DataFrame
from dataclean.types import checked
from dataclean.utils import (
    TEXT_NULL_TOKENS,
    is_null_token,
    null_token_set,
    strip_html,
)

from .cleaner import Cleaner

# A word of letters, with one apostrophe part allowed ("king's"), so each part
# of "stoke-on-trent" and "king's lynn" gets its own capital.
_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?")


# A UK postcode with or without its space: outward code, then a digit and two
# letters of inward code. Written with one space before the inward code.
_UK_POSTCODE = re.compile(r"([A-Z]{1,2}\d[A-Z\d]?) ?(\d[A-Z]{2})")


# Letters joined by spaces, dots, apostrophes and hyphens: the shape of a real
# place name. Anything else, such as "%s%s" or "<script>", is not title-cased.
_PLACE_NAME = re.compile(r"[^\W\d_]+(?:[ .'’-]+[^\W\d_]+)*\.?")


_NULL_TOKENS = null_token_set(TEXT_NULL_TOKENS)


def _collapse_whitespace(value: str) -> str:
    """Replace every run of whitespace with a single space."""
    return " ".join(value.split())


def _title_case(value: str) -> str:
    """Title-case a place name written all lower or all upper case.

    A value with mixed case, such as "McDonald Heights", is left alone since
    the writer most likely chose that casing. So is a value that does not look
    like a place name.
    """
    if not _PLACE_NAME.fullmatch(value):
        return value
    if value != value.lower() and value != value.upper():
        return value
    return _WORD.sub(lambda match: match.group().capitalize(), value.lower())


# The input role each output is made from. An output is only written when its
# input role was given a column.
_OUTPUT_INPUTS: dict[str, str] = {
    "state": "county",
    "postcode": "postcode",
    "address_line": "address_line1",
    "street": "address_line1",
    "house_no": "address_line1",
    "town": "town",
    "address_line2": "address_line2",
    "address_line3": "address_line3",
}


@checked
@dataclass
class AddressCleaner(Cleaner):
    """Cleans and splits address data spread across multiple columns.

    Consumes the input roles ``address_line1``, ``address_line2``,
    ``address_line3``, ``town``, ``county`` and ``postcode`` (all optional, so
    a row is cleaned even when its first line is empty), and produces ``state``, ``postcode``,
    ``address_line``, ``street``, ``house_no``, ``town``, ``address_line2``
    and ``address_line3`` outputs. In a pipeline an output is only written
    when its input role has a column, so a lone ``town`` column gives just a
    cleaned ``town``.

    Country columns are not part of this cleaner. ``CountryCleaner`` owns
    every country column, including the country of an address.
    """

    _given: frozenset[str] | None = None

    @override
    def fit(self, df: DataFrame, role_columns: Mapping[str, str]) -> Cleaner:
        """Return a copy that writes only the outputs whose input role has a column."""
        return replace(self, _given=frozenset(role_columns))

    @override
    def _outputs(self) -> Cleaner.OutputSchema:
        """Return the output schema: state, postcode, lines, street, house number and town.

        After ``fit``, only the outputs whose input role was given a column.
        """
        every = self._all_outputs()
        if self._given is None:
            return every
        return Cleaner.OutputSchema(
            cols=tuple(
                col
                for col in every.cols
                if _OUTPUT_INPUTS[col.name or ""] in self._given
            )
        )

    @staticmethod
    def _all_outputs() -> Cleaner.OutputSchema:
        """Return every output column, in the order ``clean_row`` returns them."""
        return Cleaner.OutputSchema(
            cols=(
                Cleaner.OutputSchema.Column(name="state", roles=("state",)),
                Cleaner.OutputSchema.Column(name="postcode", roles=("postcode",)),
                Cleaner.OutputSchema.Column(
                    name="address_line", roles=("address_line",)
                ),
                Cleaner.OutputSchema.Column(name="street", roles=("street",)),
                Cleaner.OutputSchema.Column(name="house_no", roles=("house_no",)),
                Cleaner.OutputSchema.Column(name="town", roles=("town",)),
                Cleaner.OutputSchema.Column(
                    name="address_line2", roles=("address_line2",)
                ),
                Cleaner.OutputSchema.Column(
                    name="address_line3", roles=("address_line3",)
                ),
            )
        )

    @override
    def _inputs(self) -> Cleaner.InputSchema:
        """Return the input schema for the address line, town, county and postcode columns."""
        return Cleaner.InputSchema(
            cols=(
                Cleaner.InputSchema.Column(
                    key="address_line1",
                    required=False,
                    name_hints=(
                        "address_line1",
                        "address_line",
                        "address1",
                        "address_1",
                        "addr1",
                        "street",
                    ),
                ),
                Cleaner.InputSchema.Column(
                    key="address_line2",
                    required=False,
                    name_hints=("address_line2", "address2", "address_2", "addr2"),
                ),
                Cleaner.InputSchema.Column(
                    key="address_line3",
                    required=False,
                    name_hints=("address_line3", "address3", "address_3", "addr3"),
                ),
                Cleaner.InputSchema.Column(
                    key="town", required=False, name_hints=("town", "city")
                ),
                Cleaner.InputSchema.Column(
                    key="county", required=False, name_hints=("county",)
                ),
                Cleaner.InputSchema.Column(
                    key="postcode",
                    required=False,
                    name_hints=("postcode", "post_code", "postal", "zip"),
                ),
            )
        )

    @override
    def clean_row(
        self,
        address_line1: str | None = None,
        address_line2: str | None = None,
        address_line3: str | None = None,
        town: str | None = None,
        county: str | None = None,
        postcode: str | None = None,
    ) -> str | tuple[str | None, ...] | None:  # type: ignore
        """Clean a row of address components.

        Cleans each address line, title-cases the town and county, normalizes
        the postcode, and splits the first address line into a street name and
        a leading house number.

        Args:
            address_line1: Raw primary address line, which the street and
                house number are taken from.
            address_line2: Raw secondary address line.
            address_line3: Raw tertiary address line.
            town: Raw town or city value.
            county: Raw county/state value.
            postcode: Raw postcode/zip value.

        Returns:
            A tuple of ``(state, postcode, address_line, street, house_no,
            town, address_line2, address_line3)`` with each component
            cleaned, using ``None`` where the corresponding input was missing
            or could not be parsed.
        """
        address_line = self._clean_address_line(address_line1)
        street, house_no = self._extract_street_and_number(address_line)

        everything = (
            self._clean_place(county),
            self._clean_postcode(postcode),
            address_line,
            street,
            house_no,
            self._clean_place(town),
            self._clean_address_line(address_line2),
            self._clean_address_line(address_line3),
        )
        if self._given is None:
            return everything
        kept = tuple(
            value
            for name, value in zip(_OUTPUT_INPUTS, everything, strict=True)
            if _OUTPUT_INPUTS[name] in self._given
        )
        # A single output is a plain value, as the pipeline expects.
        return kept[0] if len(kept) == 1 else kept

    # Private helper methods

    def _clean_place(self, value: str | None) -> str | None:
        """Strip HTML, collapse whitespace and title-case a town or county.

        A placeholder such as ``null`` or ``n/a`` gives None.
        """
        if not value:
            return None
        cleaned = _collapse_whitespace(strip_html(value))
        return None if is_null_token(cleaned, _NULL_TOKENS) else _title_case(cleaned)

    def _clean_address_line(self, value: str | None) -> str | None:
        """Strip HTML and collapse whitespace in an address line.

        A placeholder such as ``null`` or ``n/a`` gives None.
        """
        if not value:
            return None
        cleaned = _collapse_whitespace(strip_html(value))
        return None if is_null_token(cleaned, _NULL_TOKENS) else cleaned

    def _clean_postcode(self, value: str | None) -> str | None:
        """Strip HTML, upper-case a postcode, drop hyphens and collapse whitespace.

        A UK postcode is written with one space before its last three
        characters, so a column does not mix `SW1A1AA` and `SW1A 1AA`. Other
        postcodes keep their spacing, since the right spacing depends on the
        country. Returns None if nothing with a letter or digit is
        left, as with "???".
        """
        if not value:
            return None
        cleaned = _collapse_whitespace(strip_html(value).upper().replace("-", ""))
        if not any(char.isalnum() for char in cleaned):
            return None
        uk = _UK_POSTCODE.fullmatch(cleaned)
        return f"{uk[1]} {uk[2]}" if uk else cleaned

    def _extract_street_and_number(
        self, address_line: str | None
    ) -> tuple[str | None, str | None]:
        """Split an address line into (street, house_no).

        If the first whitespace-separated token is purely numeric, it is
        treated as the leading house number and the remaining tokens as the
        street name. Otherwise the whole address line is returned as the
        street with no house number. Returns ``(None, None)`` if
        address_line is empty.
        """
        if not address_line:
            return None, None

        addr = str(address_line).strip()
        parts = addr.split()

        if not parts:
            return None, None

        # Try to detect house number at the beginning
        house_no = None
        street = addr

        if parts[0].isdigit():
            house_no = parts[0]
            street = " ".join(parts[1:]) if len(parts) > 1 else None

        return street, house_no
