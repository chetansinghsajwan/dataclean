"""Cleaner for extracting and normalizing email addresses."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import override

from rapidfuzz.distance import OSA

from dataclean.engine import DataFrame
from dataclean.types import checked
from dataclean.utils import html_hrefs, plain_text, remove_invisible

from .cleaner import Cleaner

# Well-known mailbox providers. A domain on this list is never changed, and a
# typo is only corrected towards a domain on it.
KNOWN_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.in",
        "yahoo.co.uk",
        "ymail.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "msn.com",
        "icloud.com",
        "aol.com",
        "rediffmail.com",
        "protonmail.com",
        "proton.me",
    }
)

# Domains shorter than this allow one edit, since two edits to a short domain
# such as ``msn.com`` often give another real domain. Longer ones allow two.
_LONG_DOMAIN_LENGTH = 9
_SHORT_DOMAIN_EDITS = 1
_LONG_DOMAIN_EDITS = 2


@checked
@dataclass
class EmailCleaner(Cleaner):
    """Extracts and normalizes an email address found within a raw string.

    The address is read from the value itself, or from inside ``<...>``,
    after ``mailto:``, or before a trailing note in brackets. Of several
    addresses separated by ``;`` or ``,`` the first is used. Text around the
    address that is none of these (for example ``with space@example.com``)
    makes the value None. The address is split into local/tag/domain parts,
    optionally normalized (dot removal, tag removal, lowercasing), and
    re-assembled either as a full address or as separate components,
    depending on ``output_format``.

    Attributes:
        keep_tags: If False, strips any "+tag" suffix from the local part.
        keep_dots: If False, removes dots from the local part.
        lowercase: If True, lowercases the local part, tag, and domain.
        output_format: Whether to emit a single combined address string
            (``FULL``) or the local/tag/domain parts separately
            (``COMPONENTS``).
        strict: If True, rejects addresses that break the email standard:
            leading, trailing or doubled dots in the local part, a local part
            over 64 characters, empty or over-long (63) domain labels, labels
            that start or end with a hyphen, and a domain over 253 characters.
            If False, only the basic ``local@domain.tld`` shape is required.
            Internationalized domains are accepted either way.
        fix_domain_typos: If True, a domain that is not a known mailbox
            provider but is one or two edits (a swap counts as one) from
            exactly one, such as ``gmial.com`` or ``gmail.con``, is corrected
            to that provider (one edit for short domains, two for longer ones).
            Known domains are never changed.
    """

    class OutputFormat(StrEnum):
        """Output shape for cleaned email values."""

        FULL = "full"
        COMPONENTS = "components"

    keep_tags: bool = True
    keep_dots: bool = True
    lowercase: bool = True
    output_format: OutputFormat = OutputFormat.FULL
    strict: bool = True
    fix_domain_typos: bool = True

    _ANGLE_RE = re.compile(r"<([^<>]*@[^<>]*)>")
    _NOTE_RE = re.compile(r"\s*\([^()]*\)\s*$")
    _LOOSE_RE = re.compile(r"[A-Za-z0-9._%+-]+@[\w.-]+\.[^\W\d_]{2,}")
    _LOCAL_RE = re.compile(r"[A-Za-z0-9_%+-]+(?:\.[A-Za-z0-9_%+-]+)*")

    _MAX_LOCAL = 64
    _MAX_DOMAIN = 253
    _MAX_LABEL = 63

    @checked
    @dataclass
    class EmailComponents:
        """The parsed parts of an email address.

        Attributes:
            local: The part before the "@" (and before any "+tag").
            tag: The "+tag" suffix of the local part, if present, else None.
            domain: The part after the "@".
        """

        local: str
        tag: str | None
        domain: str

    @override
    def _outputs(self) -> Cleaner.OutputSchema:
        """Return the output schema, split into local/tag/domain columns when
        ``output_format`` is ``COMPONENTS``, or a single column otherwise."""
        if self.output_format == EmailCleaner.OutputFormat.COMPONENTS:
            return Cleaner.OutputSchema(
                cols=(
                    Cleaner.OutputSchema.Column(name="local"),
                    Cleaner.OutputSchema.Column(name="tag"),
                    Cleaner.OutputSchema.Column(name="domain"),
                )
            )

        return Cleaner.OutputSchema(cols=(Cleaner.OutputSchema.Column(),))

    @override
    def clean_row(self, v: str) -> str | tuple[str | None, ...] | None:  # type: ignore
        """Extract, normalize, and re-assemble an email address from ``v``.

        Args:
            v: The raw string to extract an email address from. In HTML, the
                ``mailto:`` links are read first, then the text with its tags
                removed.

        Returns:
            A single normalized email string when ``output_format`` is
            ``FULL``, or a ``(local, tag, domain)`` tuple when it is
            ``COMPONENTS``. Returns None if no email-shaped substring is
            found in ``v``.
        """

        # Decision: ``mailto:`` targets come first, since in HTML the link
        # target is the real address and the visible text may be a label.
        email = None
        for candidate in (*self._mailto_targets(v), plain_text(v)):
            email = self._parse_email(candidate)
            if email is not None:
                break

        if email is None:
            return None

        if not self.keep_dots:
            email = self.EmailComponents(
                local=email.local.replace(".", ""), tag=email.tag, domain=email.domain
            )

        if not self.keep_tags:
            email = self.EmailComponents(
                local=email.local, tag=None, domain=email.domain
            )

        if self.lowercase:
            email = self.EmailComponents(
                local=email.local.lower(),
                tag=email.tag.lower() if email.tag else None,
                domain=email.domain.lower(),
            )

        if self.fix_domain_typos:
            email = self.EmailComponents(
                local=email.local,
                tag=email.tag,
                domain=self._fix_domain(email.domain),
            )

        if self.output_format == "components":
            return (email.local, email.tag, email.domain)

        if email.tag is not None:
            return f"{email.local}+{email.tag}@{email.domain}"

        return f"{email.local}@{email.domain}"

    @override
    def match_score(self, df: DataFrame, cols: Iterable[str]) -> float:
        """Score confidence based on the column name containing "email".

        Args:
            df: The dataframe being inspected (unused; scoring here is
                name-based only).
            cols: Candidate column name(s); only the first is considered.

        Returns:
            1.0 if the column name contains "email", otherwise 0.0.
        """
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0
        return 1.0 if "email" in cols_tuple[0].lower() else 0.0

    @staticmethod
    def _mailto_targets(v: str) -> list[str]:
        """Return the addresses in ``mailto:`` links, without their query."""
        return [
            href[len("mailto:") :].split("?", 1)[0]
            for href in html_hrefs(v)
            if href.lower().startswith("mailto:")
        ]

    def _parse_email(self, v: str) -> EmailComponents | None:
        """Read one address out of ``v`` and split it into local/tag/domain.

        Args:
            v: The raw string holding an address, possibly wrapped.

        Returns:
            The parsed components, or None if ``v`` holds no valid address.
        """
        candidate = self._extract_candidate(v)

        if not self._is_valid(candidate):
            return None

        local, domain = candidate.split("@")

        if "+" in local:
            local, tag = local.split("+", 1)
        else:
            tag = None

        return self.EmailComponents(local=local, tag=tag, domain=domain)

    @staticmethod
    def _fix_domain(domain: str) -> str:
        """Return the known provider ``domain`` is a typo of, else ``domain``.

        A typo is one edit for a short domain and two for a longer one (a
        swap counts as one), and the provider must be strictly the closest, so
        a domain equally close to two is left as is.
        """
        lowered = domain.lower()
        if lowered in KNOWN_EMAIL_DOMAINS:
            return domain

        max_edits = (
            _LONG_DOMAIN_EDITS
            if len(lowered) >= _LONG_DOMAIN_LENGTH
            else _SHORT_DOMAIN_EDITS
        )
        distances = sorted(
            (OSA.distance(lowered, known), known) for known in KNOWN_EMAIL_DOMAINS
        )
        best, runner_up = distances[0], distances[1]
        if best[0] > max_edits or best[0] == runner_up[0]:
            return domain
        return best[1]

    def _extract_candidate(self, v: str) -> str:
        """Unwrap ``Name <a@b.com>``, ``mailto:``, lists, notes and quotes."""
        v = remove_invisible(v).strip()

        angle = self._ANGLE_RE.search(v)
        if angle:
            v = angle.group(1).strip()

        v = re.split(r"[;,]", v, maxsplit=1)[0].strip()
        v = self._NOTE_RE.sub("", v)
        v = v.removeprefix("mailto:").removeprefix("MAILTO:")
        return v.strip().strip("\"'").rstrip(".")

    def _is_valid(self, candidate: str) -> bool:
        """Check ``candidate`` against the ``strict`` or the loose rules."""
        if not self.strict:
            return self._LOOSE_RE.fullmatch(candidate) is not None

        if candidate.count("@") != 1:
            return False

        local, domain = candidate.split("@")
        if len(local) > self._MAX_LOCAL or not self._LOCAL_RE.fullmatch(local):
            return False
        if len(domain) > self._MAX_DOMAIN:
            return False

        labels = domain.split(".")
        if len(labels) < 2:
            return False
        for label in labels:
            if not 0 < len(label) <= self._MAX_LABEL:
                return False
            if label.startswith("-") or label.endswith("-"):
                return False
            if not all(c.isalnum() or c == "-" for c in label):
                return False

        tld = labels[-1]
        return len(tld) >= 2 and (tld.isalpha() or tld.startswith("xn--"))
