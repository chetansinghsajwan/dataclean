"""Tests for the per-country postcode layouts."""

import pytest

from dataclean.utils import format_postcode


@pytest.mark.parametrize(
    "value, country, expected",
    [
        ("K1A0B1", "CA", "K1A 0B1"),
        ("K1A0B1", "ca", "K1A 0B1"),
        ("1234AB", "NL", "1234 AB"),
        ("123456789", "US", "12345-6789"),
        ("00950", "PL", "00-950"),
        ("110001", "IN", "110001"),
    ],
)
def test_format_postcode_lays_out_by_country(
    value: str, country: str, expected: str
) -> None:
    assert format_postcode(value, country) == expected


@pytest.mark.parametrize(
    "value, country",
    [
        ("K1A0B1", None),
        ("K1A0B1", "ZZ"),
        ("K1A0B1", "IN"),
        ("12345", "US"),
        ("SW1A1AA", "GB"),
    ],
)
def test_format_postcode_keeps_a_value_it_cannot_place(
    value: str, country: str | None
) -> None:
    assert format_postcode(value, country) == value
