"""Tests for the shared title-casing helper."""

import pytest

from dataclean.utils import title_case

SMALL = frozenset({"of", "van"})
UPPER = frozenset({"po"})


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("ludwig VAN beethoven", "Ludwig van Beethoven"),
        ("van gogh", "Van Gogh"),
        ("anne-marie o'neil", "Anne-Marie O'Neil"),
        ("king's lynn", "King's Lynn"),
        ("mcdonald", "McDonald"),
        ("maciejewski", "Maciejewski"),
        ("12a", "12A"),
        ("1st 22nd", "1st 22nd"),
        ("po box", "PO Box"),
        ("bank of india", "Bank of India"),
    ],
)
def test_title_case(raw: str, expected: str) -> None:
    """Names are capitalised the usual way, except that small words stay lowercase and
    a chosen list of words stays uppercase.
    """
    assert title_case(raw, small_words=SMALL, upper_words=UPPER) == expected


def test_title_case_upper_cases_a_last_word_only() -> None:
    """A suffix like III is upper-cased only as the last word. At the start, iii looks
    more like a name, so it gets normal capitalisation.
    """
    last = frozenset({"iii"})

    assert title_case("john iii", upper_last_words=last) == "John III"
    assert title_case("iii john", upper_last_words=last) == "Iii John"
