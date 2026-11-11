"""Remove characters a reader cannot see."""

import re

# Zero-width space, byte order mark, word joiner and the text-direction marks
# and overrides. They are pasted in from documents and web pages and break
# matching without showing; the overrides can also reverse how a value reads.
_INVISIBLE = re.compile(r"[\ufeff\u200b\u2060\u200e\u200f\u202a-\u202e\u2066-\u2069]")
# Decision: control characters become spaces (not nothing), so "tab\there"
# keeps its two words apart instead of gluing them.
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def remove_invisible(text: str) -> str:
    """Remove zero-width spaces, byte order marks, word joiners and direction marks."""
    return _INVISIBLE.sub("", text)


def replace_control_chars(text: str, replacement: str = " ") -> str:
    """Replace control characters, such as tabs and line breaks, with ``replacement``."""
    return _CONTROL.sub(replacement, text)
