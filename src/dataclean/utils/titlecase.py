"""Title-casing shared by the cleaners that fix names and places.

The name and address cleaners both turn "ludwig van beethoven" and "stoke-on-trent"
into their usual written form. The rules live here, once, so the two cleaners
cannot drift apart. Each cleaner passes the word lists that fit its data.
"""

import re

from dataclean.types import checked

# A run of letters. Apostrophes split a word into several runs, so "o'neil"
# capitalizes each part. Hyphens and spaces are handled before this.
_LETTERS = re.compile(r"[^\W\d_]+")

# Words are split on spaces and hyphens, and both separators are kept.
_SEPARATORS = re.compile(r"([ -])")

# An ordinal such as "1st" or "22nd" stays lower case after its digits.
_ORDINAL = re.compile(r"\d+(?:st|nd|rd|th)", re.IGNORECASE)


def _case_word(
    word: str,
    index: int,
    last: bool,
    small_words: frozenset[str],
    upper_words: frozenset[str],
    upper_last_words: frozenset[str],
) -> str:
    """Title-case one word, given its position in the value."""
    lower = word.lower()
    if lower in upper_words:
        return word.upper()
    if index > 0 and lower in small_words:
        return lower
    if last and index > 0 and lower in upper_last_words:
        return word.upper()
    if any(ch.isdigit() for ch in word):
        # "12a" becomes "12A", but "1st" keeps its lower-case ending.
        return lower if _ORDINAL.fullmatch(word) else word.upper()
    cased = _LETTERS.sub(lambda match: match.group().capitalize(), lower)
    # A possessive keeps its lower-case "s": "king's lynn" becomes "King's Lynn".
    cased = re.sub(r"(?<=['’])S\b", "s", cased)
    # Decision: "Mc" is capitalized again after the prefix ("mcdonald" to
    # "McDonald"), but only when two letters follow it. "Mac" is not special-cased
    # since it is ambiguous ("Maciejewski").
    if re.match(r"Mc[a-z]{2}", cased):
        cased = "Mc" + cased[2:].capitalize()
    return cased


@checked
def title_case(
    value: str,
    small_words: frozenset[str] = frozenset(),
    upper_words: frozenset[str] = frozenset(),
    upper_last_words: frozenset[str] = frozenset(),
) -> str:
    """Title-case ``value``, one word at a time.

    Words are split on spaces and hyphens, so "stoke-on-trent" and "anne-marie"
    get a capital for each part. A word with digits is upper-cased, except an
    ordinal such as "1st".

    Args:
        value: The text to case, usually written all lower or all upper case.
        small_words: Words that stay lower case after the first word, such as
            "van" in a name or "of" in a place.
        upper_words: Words that are always upper case, such as "PO" or "NW".
        upper_last_words: Words that are upper case only as the last word,
            such as the roman numeral "iii" in "John Smith III".

    Returns:
        ``value`` in title case.
    """
    parts = _SEPARATORS.split(value)
    words = [i for i, part in enumerate(parts) if part not in (" ", "-")]
    for position, i in enumerate(words):
        parts[i] = _case_word(
            parts[i],
            position,
            position == len(words) - 1,
            small_words,
            upper_words,
            upper_last_words,
        )
    return "".join(parts)
