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

    The first email-shaped substring is located with a regex, split into
    local/tag/domain parts, optionally normalized (dot removal, tag removal,
    lowercasing), and re-assembled either as a full address or as separate
    components, depending on ``output_format``.

    Attributes:
        keep_tags: If False, strips any "+tag" suffix from the local part.
        keep_dots: If False, removes dots from the local part.
        lowercase: If True, lowercases the local part, tag, and domain.
        output_format: Whether to emit a single combined address string
            (``FULL``) or the local/tag/domain parts separately
            (``COMPONENTS``).
    """

    class OutputFormat(StrEnum):
        """Output shape for cleaned email values."""

        FULL = "full"
        COMPONENTS = "components"

    keep_tags: bool = True
    keep_dots: bool = True
    lowercase: bool = True
    output_format: OutputFormat = OutputFormat.FULL

    _EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

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
        """Locate and split the first email-shaped substring in ``v``.

        Args:
            v: The raw string to search.

        Returns:
            The parsed local/tag/domain components, or None if no
            email-shaped substring is found.
        """

        # Find iterative matches across the string quickly
        match = self._EMAIL_REGEX.search(v)

        if not match:
            return None

        email = match.group(0)

        # Safely isolate the local part and the domain name
        local, domain = email.split("@", 1)

        if "+" in local:
            local, tag = local.split("+", 1)
        else:
            tag = None

        return self.EmailComponents(local=local, tag=tag, domain=domain)
