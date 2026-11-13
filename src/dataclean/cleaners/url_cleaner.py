"""Cleaner for normalizing web addresses (URLs)."""

import ipaddress
import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Literal, override
from urllib.parse import urlsplit

from dataclean.engine import DataFrame
from dataclean.types import checked
from dataclean.utils import has_words, html_hrefs, plain_text, remove_invisible

from .cleaner import Cleaner

# Characters that carry no text but sneak into copied values.

# Where one cell holds several URLs: ";", "|", a comma followed by space, or
# the word "or". A bare comma is not a separator, it can sit inside a path.
_URL_SEPARATORS = re.compile(r"\s*[;|]\s*|,\s+|\s+or\s+", re.IGNORECASE)

# "scheme:" at the start. "example.com:8080" also matches, so a colon that is
# followed by digits is read as a port, not as a scheme.
_SCHEME = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*):(?!\d)")

# One DNS label: letters and digits (of any script), hyphens only inside.
_LABEL = re.compile(r"[^\W_](?:[^\W_]|-)*(?<!-)")

# Default ports that carry no information for the scheme.
_DEFAULT_PORTS = {"http": 80, "https": 443}

_WRAPPERS = "<>\"'`"
# Link targets that are not web addresses, so they are not read as URLs.
_NON_WEB_LINKS = ("mailto:", "tel:", "sms:", "javascript:", "#")
# Name hints: words that mark a URL column.
_NAME_TOKENS = (
    "url",
    "uri",
    "href",
    "link",
    "website",
    "web site",
    "homepage",
    "home page",
    "web address",
    "web url",
)


@checked
@dataclass
class UrlCleaner(Cleaner):
    """Normalizes a web address, tolerating common surface noise.

    Trims whitespace, invisible characters and wrapping quotes or ``<>``, adds
    ``default_scheme`` when the scheme is missing (``www.x.com``,
    ``//x.com``), lowercases the scheme and host, drops the default port
    (``:80`` for http, ``:443`` for https), a trailing dot on the host and a
    lone ``/`` after it. Path, query and fragment are kept as written, and so
    are ``www.`` and the http scheme, since removing them changes the address.

    Only ``http`` and ``https`` addresses are accepted. Other schemes
    (``javascript:``, ``mailto:``, ``ftp:``), a host that is not a valid
    domain name or IP address, and values with spaces become None. Of several
    URLs in one value, separated by ``;``, ``|``, ``, `` or ``or``, the first
    valid one is used. Internationalized hosts are kept in Unicode.

    Attributes:
        out_format: ``FULL`` renders the whole URL, ``DOMAIN`` only its host.
        default_scheme: The scheme added to a value that has none.
    """

    class Format(StrEnum):
        """Output shapes for cleaned URLs."""

        FULL = "full"
        DOMAIN = "domain"

    out_format: Format = Format.FULL
    default_scheme: Literal["http", "https"] = "https"

    _MAX_HOST: ClassVar[int] = 253
    _MAX_LABEL: ClassVar[int] = 63

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore
        """Clean ``v`` into a normalized URL, or its host for ``DOMAIN``.

        Args:
            v: The raw string holding one or more URLs. In HTML, the link
                targets (``href``) are read first, then the text with its tags
                removed.

        Returns:
            The first valid URL in ``v`` rendered per ``out_format``, or None
            if none is valid.
        """
        # Decision: ``href`` targets come first, since in HTML the link target
        # is the real address and the visible text may be a label. Targets
        # that are not web addresses (``mailto:``, ``tel:``) are skipped.
        hrefs = [h for h in html_hrefs(v) if not h.lower().startswith(_NON_WEB_LINKS)]
        for part in (*hrefs, *_URL_SEPARATORS.split(remove_invisible(plain_text(v)))):
            cleaned = self._clean_url(part.strip().strip(_WRAPPERS).strip())
            if cleaned is not None:
                return cleaned
        return None

    @override
    def match_score(
        self, df: DataFrame, cols: Iterable[str], words: tuple[str, ...]
    ) -> float:
        """Score confidence from the column name looking URL-related.

        Args:
            df: The dataframe being inspected (unused; scoring is name-based).
            cols: Candidate column name(s); only the first is considered.
            words: The lowercase words of the column name, split with the same aliases for every cleaner.

        Returns:
            1.0 if the name has a ``url``, ``uri``, ``href``, ``link``,
            ``website`` or ``homepage`` word, or ``web site``, ``web address`` or
            ``web url``, else 0.0. A name with an ``id``
            word, such as ``link_id``, scores 0.0.
        """
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0
        if has_words(words, "id"):
            return 0.0
        if any(has_words(words, hint) for hint in _NAME_TOKENS):
            return 1.0
        return 0.0

    # Private helper methods

    def _clean_url(self, value: str) -> str | None:
        """Normalize one URL candidate; None if it is not a valid web URL."""
        if not value or any(char.isspace() or not char.isprintable() for char in value):
            return None

        scheme_match = _SCHEME.match(value)
        if scheme_match is None:
            scheme = self.default_scheme
            rest = value.removeprefix("//")
        elif value[scheme_match.end() :].startswith("//"):
            scheme = scheme_match.group(1).lower()
            rest = value[scheme_match.end() + 2 :]
        else:
            return None  # "javascript:", "mailto:" and the like
        if scheme not in _DEFAULT_PORTS or not rest:
            return None

        try:
            parts = urlsplit(f"{scheme}://{rest}")
            port = parts.port
        except ValueError:
            return None

        host = self._clean_host(parts.hostname)
        if host is None:
            return None
        if self.out_format == UrlCleaner.Format.DOMAIN:
            return host

        userinfo, at, _ = parts.netloc.rpartition("@")
        netloc = f"{userinfo}{at}{host}"
        if port is not None and port != _DEFAULT_PORTS[scheme]:
            netloc += f":{port}"
        path = "" if parts.path == "/" and not parts.query else parts.path
        query = f"?{parts.query}" if parts.query else ""
        fragment = f"#{parts.fragment}" if parts.fragment else ""
        return f"{scheme}://{netloc}{path}{query}{fragment}"

    def _clean_host(self, hostname: str | None) -> str | None:
        """Return the lowercased host if it is a domain name or IP, else None."""
        if not hostname:
            return None
        host = hostname.lower().rstrip(".")
        if ":" in host:
            try:
                return f"[{ipaddress.IPv6Address(host)}]"
            except ValueError:
                return None
        try:
            return str(ipaddress.IPv4Address(host))
        except ValueError:
            pass

        labels = host.split(".")
        if len(labels) < 2 or len(host) > self._MAX_HOST:
            return None
        if not all(
            _LABEL.fullmatch(label) and len(label) <= self._MAX_LABEL
            for label in labels
        ):
            return None
        tld = labels[-1]
        if not (tld.startswith("xn--") or (len(tld) >= 2 and not tld.isdigit())):
            return None
        return host
