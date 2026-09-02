import re
from enum import StrEnum

from dataclean.types import checked


class TextCase(StrEnum):
    UPPER = "upper"
    LOWER = "lower"
    CAMEL = "camel"
    PASCAL = "pascal"
    SNAKE = "snake"
    KEBAB = "kebab"


@checked
def convert_to_case(v: str, case: TextCase) -> str:
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
    # split on non-alphanumeric, and camelCase boundaries
    v = re.sub(r"[_\-\s]+", " ", v)
    v = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", v)
    return [w for w in v.split(" ") if w]


def convert_to_upper_case(v: str) -> str:
    return v.upper()


def convert_to_lower_case(v: str) -> str:
    return v.lower()


def convert_to_camel_case(v: str) -> str:
    words = _split_words(v)
    if not words:
        return v
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


def convert_to_pascal_case(v: str) -> str:
    return "".join(w.capitalize() for w in _split_words(v))


def convert_to_snake_case(v: str) -> str:
    return "_".join(w.lower() for w in _split_words(v))


def convert_to_kebab_case(v: str) -> str:
    return "-".join(w.lower() for w in _split_words(v))
