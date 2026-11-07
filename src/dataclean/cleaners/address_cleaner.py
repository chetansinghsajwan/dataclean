"""Address cleaner for handling multi-column address data."""

import re
from dataclasses import dataclass
from typing import override

from dataclean.types import checked

from .cleaner import Cleaner

# A word of letters, with one apostrophe part allowed ("king's"), so each part
# of "stoke-on-trent" and "king's lynn" gets its own capital.
_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?")


# Letters joined by spaces, dots, apostrophes and hyphens: the shape of a real
# place name. Anything else, such as "%s%s" or "<script>", is not title-cased.
_PLACE_NAME = re.compile(r"[^\W\d_]+(?:[ .'’-]+[^\W\d_]+)*\.?")


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


@checked
@dataclass
class AddressCleaner(Cleaner):
    """Cleans and splits address data spread across multiple columns.

    Consumes the input roles ``address_line1``, ``address_line2``,
    ``address_line3``, ``town``, ``county`` and ``postcode`` (all optional, so
    a row is cleaned even when its first line is empty), and produces ``state``, ``postcode``,
    ``address_line``, ``street``, ``house_no``, ``town``, ``address_line2``
    and ``address_line3`` outputs.

    Country columns are not part of this cleaner. ``CountryCleaner`` owns
    every country column, including the country of an address.
    """

    @override
    def _outputs(self) -> Cleaner.OutputSchema:
        """Return the output schema: state, postcode, lines, street, house number and town."""
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
    ) -> tuple[str | None, ...] | None:  # type: ignore
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

        return (
            self._clean_place(county),
            self._clean_postcode(postcode),
            address_line,
            street,
            house_no,
            self._clean_place(town),
            self._clean_address_line(address_line2),
            self._clean_address_line(address_line3),
        )

    # Private helper methods

    def _clean_place(self, value: str | None) -> str | None:
        """Collapse whitespace and title-case a town or county; None if empty."""
        if not value:
            return None
        return _title_case(_collapse_whitespace(value)) or None

    def _clean_address_line(self, value: str | None) -> str | None:
        """Collapse whitespace in an address line; None if empty."""
        if not value:
            return None
        return _collapse_whitespace(value) or None

    def _clean_postcode(self, value: str | None) -> str | None:
        """Upper-case a postcode, drop hyphens and collapse whitespace.

        Spacing inside the postcode is kept, since the right spacing depends
        on the country. Returns None if nothing with a letter or digit is
        left, as with "???".
        """
        if not value:
            return None
        cleaned = _collapse_whitespace(value.upper().replace("-", ""))
        return cleaned if any(char.isalnum() for char in cleaned) else None

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
