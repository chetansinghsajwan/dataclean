"""Text case conversion helpers (upper, lower, camel, pascal, snake, kebab)."""

import re
from enum import StrEnum

from dataclean.types import checked


class TextCase(StrEnum):
    """Identifies a text casing style for use with :func:`convert_to_case`.

    Attributes:
        UPPER: ``UPPERCASE``.
        LOWER: ``lowercase``.
        CAMEL: ``camelCase``.
        PASCAL: ``PascalCase``.
        SNAKE: ``snake_case``.
        KEBAB: ``kebab-case``.
    """

    UPPER = "upper"
    LOWER = "lower"
    CAMEL = "camel"
    PASCAL = "pascal"
    SNAKE = "snake"
    KEBAB = "kebab"


@checked
def convert_to_case(v: str, case: TextCase) -> str:
    """Convert ``v`` to the given :class:`TextCase` style.

    Args:
        v: The string to convert.
        case: The target casing style.

    Returns:
        ``v`` rewritten in the requested case.

    Raises:
        ValueError: If ``case`` is not a recognized :class:`TextCase` value.
    """
    match case:
        case TextCase.UPPER:
            return convert_to_upper_case(v)

        case TextCase.LOWER:
            return convert_to_lower_case(v)

        case TextCase.CAMEL:
            return convert_to_camel_case(v)

        case TextCase.PASCAL:
            return convert_to_pascal_case(v)

        case TextCase.SNAKE:
            return convert_to_snake_case(v)

        case TextCase.KEBAB:
            return convert_to_kebab_case(v)

    raise ValueError(f"Unsupported text case: {case}")


def _split_words(v: str) -> list[str]:
    """Split ``v`` into words on separators, whitespace, and camelCase boundaries."""
    # split on non-alphanumeric, and camelCase boundaries
    v = re.sub(r"[_\-\s]+", " ", v)
    v = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", v)
    return [w for w in v.split(" ") if w]


def convert_to_upper_case(v: str) -> str:
    """Return ``v`` converted to UPPERCASE."""
    return v.upper()


def convert_to_lower_case(v: str) -> str:
    """Return ``v`` converted to lowercase."""
    return v.lower()


def convert_to_camel_case(v: str) -> str:
    """Return ``v`` converted to camelCase. Returns ``v`` unchanged if it has no words."""
    words = _split_words(v)
    if not words:
        return v
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


def convert_to_pascal_case(v: str) -> str:
    """Return ``v`` converted to PascalCase."""
    return "".join(w.capitalize() for w in _split_words(v))


def convert_to_snake_case(v: str) -> str:
    """Return ``v`` converted to snake_case."""
    return "_".join(w.lower() for w in _split_words(v))


def convert_to_kebab_case(v: str) -> str:
    """Return ``v`` converted to kebab-case."""
    return "-".join(w.lower() for w in _split_words(v))
