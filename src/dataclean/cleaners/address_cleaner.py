"""Address cleaner for handling multi-column address data."""

from dataclasses import dataclass
from typing import override

from dataclean.types import checked

from .cleaner import Cleaner


@checked
@dataclass
class AddressCleaner(Cleaner):
    """Cleans and splits address data spread across multiple columns.

    Consumes the input roles ``county``, ``country``, ``address_line1``,
    ``address_line2``, and ``address_line3`` (only ``address_line1`` is
    required), and produces ``country``, ``state``, ``postcode``,
    ``address_line``, ``street``, and ``house_no`` outputs.
    """

    @override
    def _outputs(self) -> Cleaner.OutputSchema:
        """Return the output schema: country, state, postcode, address_line, street, house_no."""
        return Cleaner.OutputSchema(
            cols=(
                Cleaner.OutputSchema.Column(name="country", roles=("country",)),
                Cleaner.OutputSchema.Column(name="state", roles=("state",)),
                Cleaner.OutputSchema.Column(name="postcode", roles=("postcode",)),
                Cleaner.OutputSchema.Column(
                    name="address_line", roles=("address_line",)
                ),
                Cleaner.OutputSchema.Column(name="street", roles=("street",)),
                Cleaner.OutputSchema.Column(name="house_no", roles=("house_no",)),
            )
        )

    @override
    def _inputs(self) -> Cleaner.InputSchema:
        """Return the input schema for county/country/address line columns."""
        return Cleaner.InputSchema(
            cols=(
                Cleaner.InputSchema.Column(
                    key="county", required=False, name_hints=("county",)
                ),
                Cleaner.InputSchema.Column(
                    key="country",
                    required=False,
                    name_hints=("country",),
                ),
                Cleaner.InputSchema.Column(
                    key="address_line1",
                    name_hints=("address_line1", "address_line", "street"),
                ),
                Cleaner.InputSchema.Column(
                    key="address_line2",
                    required=False,
                    name_hints=("address_line2", "city"),
                ),
                Cleaner.InputSchema.Column(
                    key="address_line3",
                    required=False,
                    name_hints=("address_line3", "postcode", "zip"),
                ),
            )
        )

    @override
    def clean_row(
        self,
        county: str | None = None,
        country: str | None = None,
        address_line1: str | None = None,
        address_line2: str | None = None,
        address_line3: str | None = None,
    ) -> tuple[str | None, ...] | None:  # type: ignore
        """Clean a row of address components.

        Standardizes the country and county/state names, cleans the
        primary address line, normalizes the postcode, and attempts to
        split the address line into a street name and leading house
        number.

        Args:
            county: Raw county/state value.
            country: Raw country value.
            address_line1: Raw primary address line, treated as the main
                address line to derive street/house number from.
            address_line2: Raw secondary address line. Currently unused by
                this implementation.
            address_line3: Raw tertiary address line, expected to hold the
                postcode/zip.

        Returns:
            A tuple of ``(country, county, postcode, address_line, street,
            house_no)`` with each component cleaned, using ``None`` where
            the corresponding input was missing or could not be parsed.
        """
        # Extract and clean individual components
        country = self._clean_country(country)
        county = self._clean_county(county)
        address_line = self._clean_address_line(address_line1)
        postcode = self._clean_postcode(address_line3)

        # Try to extract street and house number from address line
        street, house_no = self._extract_street_and_number(address_line)

        return (country, county, postcode, address_line, street, house_no)

    # Private helper methods

    def _clean_country(self, value: str | None) -> str | None:
        """Strip and title-case the country value; returns None if empty."""
        if not value:
            return None
        return str(value).strip().title()

    def _clean_county(self, value: str | None) -> str | None:
        """Strip and title-case the county/state value; returns None if empty."""
        if not value:
            return None
        return str(value).strip().title()

    def _clean_address_line(self, value: str | None) -> str | None:
        """Strip the main address line; returns None if empty."""
        if not value:
            return None
        return str(value).strip()

    def _clean_city(self, value: str | None) -> str | None:
        """Strip and title-case the city value; returns None if empty."""
        if not value:
            return None
        return str(value).strip().title()

    def _clean_postcode(self, value: str | None) -> str | None:
        """Strip, upper-case, and remove hyphens from the postcode value.

        Returns None if the input is empty, or if it becomes empty after
        cleaning.
        """
        if not value:
            return None
        cleaned = str(value).strip().upper()
        # Remove common formatting like hyphens
        cleaned = cleaned.replace("-", "")
        return cleaned if cleaned else None

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
