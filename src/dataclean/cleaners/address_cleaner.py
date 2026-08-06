"""Address cleaner for handling multi-column address data."""

from collections.abc import Mapping
from typing import override

from dataclean.cleaners.base_cleaner import CellValue
from dataclean.cleaners.group_cleaner import ColumnRole, GroupCleaner
from dataclean.engine.dataframe import DataType


class AddressCleaner(GroupCleaner, frozen=True):
    """
    Cleans address data from multiple columns.

    Expects input roles: county, country, address_line1, address_line2, address_line3
    Produces outputs: country, state, postcode, address_line, street, house_no
    """

    @override
    def name(self) -> str:
        return "AddressCleaner"

    @override
    def provided_roles(self) -> tuple[str, ...]:
        return ("address", "country", "state", "postcode")

    @override
    def output_schema(self) -> tuple[tuple[str, DataType], ...]:
        return (
            ("country", "str"),
            ("state", "str"),
            ("postcode", "str"),
            ("address_line", "str"),
            ("street", "str"),
            ("house_no", "str"),
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
                required=False,
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
        self, values: Mapping[str, CellValue | None]
    ) -> tuple[CellValue | None, ...] | None:
        """
        Clean a row of address components.

        Validates and standardizes address data.
        Returns: (country, state, postcode, address_line, street, house_no)
        """
        # Extract and clean individual components
        country = self._clean_country(values.get("country"))
        county = self._clean_county(values.get("county"))
        address_line = self._clean_address_line(values.get("address_line1"))
        postcode = self._clean_postcode(values.get("address_line3"))

        # Try to extract street and house number from address line
        street, house_no = self._extract_street_and_number(address_line)

        return (country, county, postcode, address_line, street, house_no)

    @override
    def group_confidence(self, role_scores: Mapping[str, float]) -> float:
        """Compute confidence that all matched roles belong to an address."""
        if not role_scores:
            return 0.0

        # Average confidence of matched roles
        return sum(role_scores.values()) / len(role_scores)

    # Private helper methods

    def _clean_country(self, value: CellValue | None) -> CellValue | None:
        """Clean country field."""
        if not value:
            return None
        return str(value).strip().title()

    def _clean_county(self, value: CellValue | None) -> CellValue | None:
        """Clean state/county field."""
        if not value:
            return None
        return str(value).strip().title()

    def _clean_address_line(self, value: CellValue | None) -> CellValue | None:
        """Clean main address line."""
        if not value:
            return None
        return str(value).strip()

    def _clean_city(self, value: CellValue | None) -> CellValue | None:
        """Clean city field."""
        if not value:
            return None
        return str(value).strip().title()

    def _clean_postcode(self, value: CellValue | None) -> CellValue | None:
        """Clean postcode/zip field."""
        if not value:
            return None
        cleaned = str(value).strip().upper()
        # Remove common formatting like hyphens
        cleaned = cleaned.replace("-", "")
        return cleaned if cleaned else None

    def _extract_street_and_number(
        self, address_line: CellValue | None
    ) -> tuple[CellValue | None, CellValue | None]:
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
