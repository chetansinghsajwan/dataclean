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
    assert split_words(name) == expected
