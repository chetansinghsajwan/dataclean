"""Tests splitting column names into words."""

import pytest

from dataclean.utils import ends_with_words, has_words, split_words, starts_with_words


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


def test_has_words_matches_whole_words_only() -> None:
    assert has_words(("home", "tel"), "tel")
    assert not has_words(("hotel",), "tel")
    assert has_words(("home", "post", "code"), "post_code")
    assert not has_words(("post", "office", "code"), "post_code")


def test_has_words_allows_a_plural_last_word() -> None:
    assert has_words(("user", "comments"), "comment")
    assert not has_words(("user", "comment"), "comments")


def test_starts_and_ends_with_words() -> None:
    assert starts_with_words(("is", "active"), "is")
    assert not starts_with_words(("this", "active"), "is")
    assert ends_with_words(("user", "status"), "status")
    assert not ends_with_words(("status", "user"), "status")
