"""Address cleaner for handling multi-column address data."""

from typing import override

from dataclean.cleaners.cleaner import Cleaner, ColumnRole
from dataclean.engine.dataframe import DataType


class AddressCleaner(Cleaner):
    """
    Cleans address data from multiple columns.

    Expects input roles: county, country, address_line1, address_line2, address_line3
    Produces outputs: country, state, postcode, address_line, street, house_no
    """

    @override
    def provided_roles(self) -> tuple[str, ...]:
        return ("address", "country", "state", "postcode")

    @override
    def output_schema(self) -> tuple[tuple[str, DataType], ...]:
        return (
            ("country", DataType.STR),
            ("state", DataType.STR),
            ("postcode", DataType.STR),
            ("address_line", DataType.STR),
            ("street", DataType.STR),
            ("house_no", DataType.STR),
        )

    @override
    def input_roles(self) -> tuple[ColumnRole, ...]:
        return (
            ColumnRole(key="county", required=False, name_hints=("county",)),
            ColumnRole(
                key="country",
                required=False,
                name_hints=("country",),
            ),
            ColumnRole(
                key="address_line1",
                name_hints=("address_line1", "address_line", "street"),
            ),
            ColumnRole(
                key="address_line2",
                required=False,
                name_hints=("address_line2", "city"),
            ),
            ColumnRole(
                key="address_line3",
                required=False,
                name_hints=("address_line3", "postcode", "zip"),
            ),
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
        """
        Clean a row of address components.

        Validates and standardizes address data.
        Returns: (country, state, postcode, address_line, street, house_no)
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
        """Clean country field."""
        if not value:
            return None
        return str(value).strip().title()

    def _clean_county(self, value: str | None) -> str | None:
        """Clean state/county field."""
        if not value:
            return None
        return str(value).strip().title()

    def _clean_address_line(self, value: str | None) -> str | None:
        """Clean main address line."""
        if not value:
            return None
        return str(value).strip()

    def _clean_city(self, value: str | None) -> str | None:
        """Clean city field."""
        if not value:
            return None
        return str(value).strip().title()

    def _clean_postcode(self, value: str | None) -> str | None:
        """Clean postcode/zip field."""
        if not value:
            return None
        cleaned = str(value).strip().upper()
        # Remove common formatting like hyphens
        cleaned = cleaned.replace("-", "")
        return cleaned if cleaned else None

    def _extract_street_and_number(
        self, address_line: str | None
    ) -> tuple[str | None, str | None]:
        """Extract street name and house number from address line."""
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
