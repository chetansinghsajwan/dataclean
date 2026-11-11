"""Placeholder text that stands for "no value", shared by the cleaners."""

from collections.abc import Iterable

# Placeholders spreadsheets and databases write for a missing value. Some of
# them are real data in some columns ("Na" is a surname, "NA" is Namibia), so
# a cleaner picks the tokens that are safe for its own kind of column.
COMMON_NULL_TOKENS: tuple[str, ...] = (
    "null",
    "none",
    "nan",
    "undefined",
    "n/a",
    "na",
    "-",
    "''",
    '""',
)


# The placeholders that are safe to drop from names and address parts. "na"
# and "nan" are left out since they are real names and the Namibia code.
TEXT_NULL_TOKENS: tuple[str, ...] = ("null", "none", "undefined", "n/a", "-")


def null_token_set(tokens: Iterable[str]) -> frozenset[str]:
    """Build the lookup set for :func:`is_null_token`, lower-cased once."""
    return frozenset(token.lower() for token in tokens)


def is_null_token(value: str, tokens: frozenset[str]) -> bool:
    """Return True if ``value`` is empty or one of ``tokens``, ignoring case.

    Args:
        value: The text to test, already stripped.
        tokens: A set built with :func:`null_token_set`.
    """
    return not value or value.lower() in tokens
