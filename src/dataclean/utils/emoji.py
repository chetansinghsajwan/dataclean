"""Remove emoji from text, for the cleaners whose values are never emoji."""

import re

# Characters that show as an emoji. Plain text symbols such as the copyright,
# registered and trademark signs, digits and "#" are not listed, so they stay.
_BASE = (
    "[\U0001f000-\U0001faff"  # games, pictographs, faces, transport, flags
    "\u2600-\u27bf"  # weather, hearts, check marks and other dingbats
    "\u231a\u231b\u23e9-\u23f3\u23f8-\u23fa"  # watch, hourglass, media controls
    "\u2b05-\u2b07\u2b1b\u2b1c\u2b50\u2b55"  # arrows, squares, star, circle
    "\u2194-\u2199\u21a9\u21aa\u2934\u2935"  # arrows with an emoji look
    "\u25aa\u25ab\u25b6\u25c0\u25fb-\u25fe"  # small shapes and play buttons
    "\u3030\u303d\u3297\u3299]"
)
_SKIN_OR_VARIANT = "[\U0001f3fb-\U0001f3ff\ufe0f]*"

# One emoji, with its skin tone or variation selector, and any further emoji
# joined to it by a zero-width joiner ("family", "woman technologist").
_SEQUENCE = f"{_BASE}{_SKIN_OR_VARIANT}(?:\u200d{_BASE}{_SKIN_OR_VARIANT})*"

# A keycap such as "1" in a box, then the emoji sequence, then the tag
# characters that spell a regional flag such as England, then a stray
# variation selector.
_EMOJI = re.compile(
    rf"[0-9#*]\ufe0f?\u20e3|{_SEQUENCE}|[\U000e0020-\U000e007f]+|\ufe0f"
)


def remove_emoji(value: str) -> str:
    """Remove every emoji from ``value``, leaving the rest as it was.

    Decision: the zero-width joiner is removed only inside an emoji sequence.
    Indic and Persian scripts need it between letters, so a stray one is kept.
    Spaces left behind are not collapsed, since each cleaner collapses them
    in its own step.

    Args:
        value: The text to clean.

    Returns:
        ``value`` without emoji, skin tone modifiers, flags and keycaps.
    """
    return _EMOJI.sub("", value)
