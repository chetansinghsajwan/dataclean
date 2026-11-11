"""Split names such as column names into their words."""

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
