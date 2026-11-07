"""Cleaner for extracting and normalizing email addresses."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import override

from dataclean.engine import DataFrame
from dataclean.types import checked

from .cleaner import Cleaner


# TODO: Need to add functionality to parse display name
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

    _INVISIBLE_RE = re.compile("[\ufeff\u200b\u2060]")
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
            v: The raw string to extract an email address from.

        Returns:
            A single normalized email string when ``output_format`` is
            ``FULL``, or a ``(local, tag, domain)`` tuple when it is
            ``COMPONENTS``. Returns None if no email-shaped substring is
            found in ``v``.
        """

        email = self._parse_email(v)

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

    def _extract_candidate(self, v: str) -> str:
        """Unwrap ``Name <a@b.com>``, ``mailto:``, lists, notes and quotes."""
        v = self._INVISIBLE_RE.sub("", v).strip()

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
