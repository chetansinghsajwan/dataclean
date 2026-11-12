"""Address cleaner for handling multi-column address data."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import override

from dataclean.engine import DataFrame
from dataclean.types import checked
from dataclean.utils import (
    TEXT_NULL_TOKENS,
    format_postcode,
    is_null_token,
    looks_like_code,
    looks_like_link,
    looks_like_path,
    null_token_set,
    remove_emoji,
    strip_html,
    title_case,
)

from .cleaner import Cleaner
from .country_cleaner import CountryCleaner

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


# Words that stay lower case inside a place or street name, as in
# "Stoke-on-Trent", "District of Columbia" and "Île-de-France".
_SMALL_WORDS = frozenset(
    "a an and at by de del der des di du el en for in la las le les of on or sur the to upon van von y".split()
)

# Words that are always upper case in an address: a box, the UK and the
# compass points ("PO Box 7", "Unit 4, Leeds NW").
_UPPER_WORDS = frozenset("po pmb uk usa ne nw se sw".split())

# Values longer than this are free text or an attack, not an address part.
# Decision: null them rather than keep a long junk value.
_MAX_LENGTH = 200


def _is_junk(value: str) -> bool:
    """Whether ``value`` is code, a link or a path, which no address part is."""
    return looks_like_code(value) or looks_like_link(value) or looks_like_path(value)


def _title_case(value: str) -> str:
    """Title-case an address part written all lower or all upper case.

    A value with mixed case, such as "McDonald Heights", is left alone since
    the writer most likely chose that casing. So is a value that does not look
    like a place name. Decision: only uniform case is changed, since mixed case
    is usually deliberate and a guess would damage names.
    """
    if value != value.lower() and value != value.upper():
        return value
    return title_case(value, small_words=_SMALL_WORDS, upper_words=_UPPER_WORDS)


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
    cleaned ``town``. Decision: outputs follow the columns given, so the
    cleaner never adds empty columns the data did not have.

    Country columns are not part of this cleaner. ``CountryCleaner`` owns
    every country column, including the country of an address.
    """

    _given: frozenset[str] | None = None
    _country_cleaner: CountryCleaner = field(
        init=False,
        repr=False,
        compare=False,
        default_factory=lambda: CountryCleaner(out_format=CountryCleaner.Format.ALPHA2),
    )

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
                # Read from the country column cleaned in the same table. It is
                # never matched by name, so the column stays with CountryCleaner.
                Cleaner.InputSchema.Column(
                    key="country", required=False, context_only=True
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
        country: str | None = None,
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
            country: Optional country of the address (name or ISO code),
                used to lay the postcode out the way that country writes it.

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
            self._clean_postcode(postcode, country),
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

        A placeholder such as ``null`` or ``n/a``, a value with no letters and
        junk such as code, a link or a path give None.
        """
        if not value:
            return None
        cleaned = _collapse_whitespace(remove_emoji(strip_html(value)))
        if is_null_token(cleaned, _NULL_TOKENS) or not any(
            char.isalpha() for char in cleaned
        ):
            return None
        if len(cleaned) > _MAX_LENGTH or _is_junk(cleaned):
            return None
        return _title_case(cleaned)

    def _clean_address_line(self, value: str | None) -> str | None:
        """Strip HTML, collapse whitespace and title-case an address line.

        A placeholder such as ``null`` or ``n/a``, a value with no letter or
        digit and junk such as code, a link or a path give None.
        """
        if not value:
            return None
        cleaned = _collapse_whitespace(remove_emoji(strip_html(value)))
        if is_null_token(cleaned, _NULL_TOKENS) or not any(
            char.isalnum() for char in cleaned
        ):
            return None
        if len(cleaned) > _MAX_LENGTH or _is_junk(cleaned):
            return None
        return _title_case(cleaned)

    def _alpha2(self, country: str | None) -> str | None:
        """Return the ISO alpha-2 code of ``country``, or None if it is unknown."""
        if country is None or not country.strip():
            return None
        return self._country_cleaner.clean_row(country.strip())

    def _clean_postcode(
        self, value: str | None, country: str | None = None
    ) -> str | None:
        """Strip HTML, upper-case a postcode, drop hyphens and collapse whitespace.

        A UK postcode is written with one space before its last three
        characters, so a column does not mix `SW1A1AA` and `SW1A 1AA`. Other
        postcodes keep their spacing, since the right spacing depends on the
        country. When the row's country is known, the postcode is laid out as
        that country writes it, such as "K1A 0B1" in Canada or "12345-6789" in
        the United States. A postcode that does not fit its country's pattern
        is kept as cleaned. Returns None if nothing with a letter or digit is
        left, as with "???".
        """
        if not value:
            return None
        cleaned = _collapse_whitespace(
            remove_emoji(strip_html(value)).upper().replace("-", "")
        )
        if not any(char.isalnum() for char in cleaned):
            return None
        uk = _UK_POSTCODE.fullmatch(cleaned)
        if uk:
            return f"{uk[1]} {uk[2]}"
        return (
            format_postcode(cleaned.replace(" ", ""), self._alpha2(country))
            if country
            else cleaned
        )

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
