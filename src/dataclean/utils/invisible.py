"""Remove characters a reader cannot see."""

import re

# Zero-width space, byte order mark and word joiner. They are pasted in from
# documents and web pages and break matching without showing.
_INVISIBLE = re.compile("[﻿​⁠]")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def remove_invisible(text: str) -> str:
    """Remove zero-width spaces, byte order marks and word joiners."""
    return _INVISIBLE.sub("", text)


def replace_control_chars(text: str, replacement: str = " ") -> str:
    """Replace control characters, such as tabs and line breaks, with ``replacement``."""
    return _CONTROL.sub(replacement, text)
