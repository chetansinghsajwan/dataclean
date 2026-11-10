"""Remove HTML markup from text."""

import re

# Elements whose content is code or hidden data, not text a reader would see.
# Other elements, such as headings and paragraphs, keep their content.
_DROPPED_ELEMENTS = (
    "script",
    "style",
    "noscript",
    "template",
    "iframe",
    "object",
    "embed",
    "applet",
)

# In order of preference at each position: a comment, a dropped element with
# its content (to the end of the text when it is never closed), a declaration
# such as ``<!DOCTYPE html>``, then any other tag. A tag name ends at a space,
# ``/`` or ``>``, so text like ``a < b``, ``<https://x.com>`` and
# ``<john@example.com>`` is not touched.
_MARKUP_RE = re.compile(
    r"<!--.*?-->"
    rf"|<(?P<dropped>{'|'.join(_DROPPED_ELEMENTS)})\b[^<>]*>.*?(?:</(?P=dropped)\s*>|$)"
    r"|<[!?][^<>]*>"
    r"|</?[A-Za-z][A-Za-z0-9-]*(?=[\s/>])[^<>]*>",
    re.DOTALL | re.IGNORECASE,
)


def strip_html(text: str, replacement: str = " ") -> str:
    """Remove HTML tags from ``text``, and the content of non-text elements.

    Tags, comments and declarations are removed but the text inside headings,
    paragraphs, links and the like is kept. For ``script``, ``style`` and a few
    other elements that hold code or hidden data, the content is removed too.

    Args:
        text: The text that may hold HTML.
        replacement: What each removed piece is replaced by. The default keeps
            words on either side of a tag apart.

    Returns:
        The text without markup. Entities such as ``&amp;`` are left as is.
    """
    return _MARKUP_RE.sub(replacement, text)
