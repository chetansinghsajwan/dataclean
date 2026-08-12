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
    class OutputFormat(StrEnum):
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
        local: str
        tag: str | None
        domain: str

    @override
    def _outputs(self) -> Cleaner.OutputSchema:
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
        """
        Clean the input email value and return the cleaned email.
        If the value cannot be cleaned, return None.

        This method implements specific cleaning logic for email addresses, such as trimming whitespace and validating the format.

        Args:
            v (str): The input email value to be cleaned.

        Returns:
            str | None: The cleaned email, or None if the value cannot be cleaned.
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
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0
        return 1.0 if "email" in cols_tuple[0].lower() else 0.0

    def _parse_email(self, v: str) -> EmailComponents | None:

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
