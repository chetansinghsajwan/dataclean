"""Tests splitting column names into words."""

import pytest

from dataclean.utils import split_words


@pytest.mark.parametrize(
    "name, expected",
    [
        ("created_at", ("created", "at")),
        ("createdAt", ("created", "At")),
        ("createdat", ("created", "at")),
        ("last-login_time", ("last", "login", "time")),
        ("address1", ("address", "1")),
        # A name it does not recognise stays whole.
        ("format", ("format",)),
        ("seat", ("seat",)),
        ("", ()),
    ],
)
def test_split_words(name: str, expected: tuple[str, ...]) -> None:
    """Column names are split on underscores, hyphens and changes in case. That way
    differently styled names, like first_name and firstName, compare as the same
    words.
    """
    assert split_words(name) == expected
