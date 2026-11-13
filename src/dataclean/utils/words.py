"""Split names such as column names into their words."""

import re
from functools import lru_cache

import wordninja


def split_words(name: str) -> tuple[str, ...]:
    """Split ``name`` into words, keeping their case.

    It splits on separators, camelCase and digits, and breaks glued names into
    common English words, so ``created_at``, ``createdAt`` and ``createdat``
    all contain the word ``at``. A name it does not recognise stays whole.

    Decision: this wraps the ``wordninja`` library instead of a hand-written
    regex, so glued names are split by word frequency and one shared helper
    serves every cleaner that reads column names.

    Args:
        name: The text to split, such as a column name.

    Returns:
        The words in order.
    """
    return tuple(wordninja.split(name))


@lru_cache(maxsize=1024)
def _phrase_words(phrase: str) -> tuple[str, ...]:
    """Split a hint such as ``post_code`` into lowercase words, once per hint.

    Decision: a hint is split only on separators and digits, not by word
    frequency, so what is written is what is matched. Write ``post code``,
    not ``postcode``, since column names reach the cleaners as split words.
    """
    return tuple(re.findall(r"[a-z]+|\d+", phrase.lower()))


def _same_word(word: str, hint: str) -> bool:
    """Whether ``word`` is ``hint``, or its plural with a trailing ``s``."""
    return word == hint or (word.endswith("s") and word[:-1] == hint)


def has_words(words: tuple[str, ...], phrase: str) -> bool:
    """Whether the lowercase ``words`` of a column name contain ``phrase``.

    Decision: a hint matches whole words only, so ``tel`` matches ``home_tel``
    but not ``hotel``. A hint of several words (``post_code``) must appear
    in a row, and the last word may carry a plural ``s`` (``comments``).

    Args:
        words: The lowercase words of the column name.
        phrase: The hint, as one word or several joined by separators.
    """
    hint = _phrase_words(phrase)
    size = len(hint)
    if not hint or size > len(words):
        return False
    for start in range(len(words) - size + 1):
        chunk = words[start : start + size]
        if chunk[:-1] == hint[:-1] and _same_word(chunk[-1], hint[-1]):
            return True
    return False


def starts_with_words(words: tuple[str, ...], phrase: str) -> bool:
    """Whether the lowercase ``words`` begin with ``phrase`` (see ``has_words``)."""
    hint = _phrase_words(phrase)
    if not hint or len(hint) > len(words):
        return False
    chunk = words[: len(hint)]
    return chunk[:-1] == hint[:-1] and _same_word(chunk[-1], hint[-1])


def ends_with_words(words: tuple[str, ...], phrase: str) -> bool:
    """Whether the lowercase ``words`` end with ``phrase`` (see ``has_words``)."""
    hint = _phrase_words(phrase)
    if not hint or len(hint) > len(words):
        return False
    chunk = words[len(words) - len(hint) :]
    return chunk[:-1] == hint[:-1] and _same_word(chunk[-1], hint[-1])
