"""Remove HTML markup from text."""

import html
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
_HIDDEN = (
    r"<!--.*?-->"
    rf"|<(?P<dropped>{'|'.join(_DROPPED_ELEMENTS)})\b[^<>]*>.*?(?:</(?P=dropped)\s*>|$)"
)
_MARKUP_RE = re.compile(
    rf"{_HIDDEN}"
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


_HIDDEN_RE = re.compile(_HIDDEN, re.DOTALL | re.IGNORECASE)
_HREF_RE = re.compile(
    r"<a\b[^<>]*?\bhref\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s<>\"']+))",
    re.DOTALL | re.IGNORECASE,
)


def html_hrefs(text: str) -> tuple[str, ...]:
    """Return the ``href`` values of the links in ``text``, in order.

    Links inside comments and non-text elements such as ``script`` are
    ignored. Entities in a value, such as ``&amp;``, are decoded. Values are
    returned as written, so ``mailto:``, ``tel:`` and ``#anchor`` targets are
    included for the caller to pick from.

    Args:
        text: The text that may hold HTML.

    Returns:
        The stripped ``href`` values; empty ones are left out.
    """
    visible = _HIDDEN_RE.sub(" ", text)
    values = (html.unescape("".join(m)).strip() for m in _HREF_RE.findall(visible))
    return tuple(value for value in values if value)
