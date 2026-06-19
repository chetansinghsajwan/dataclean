import re
from typing import override

from dataclean.engine.dataframe import DataFrame, DataType
from dataclean.types import StrictBaseModel

from .base_cleaner import BaseCleaner


# TODO: Need to add functionality to parse display name
class EmailCleaner(BaseCleaner, frozen=True):
    keep_tags: bool = True
    keep_dots: bool = True
    lowercase: bool = True

    _EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

    class EmailComponents(StrictBaseModel, frozen=True):
        local: str
        tag: str | None
        domain: str

    @override
    def name(self) -> str:
        return "EmailCleaner"

    @override
    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]:
        if self.split_components:
            return (("local", "str"), ("tag", "str"), ("domain", "str"))

        return "str"

    @override
    def clean_value(self, v: str) -> str | None:
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

        if self.split_components:
            return (email.local, email.tag, email.domain)

        if email.tag is not None:
            return f"{email.local}+{email.tag}@{email.domain}"

        return f"{email.local}@{email.domain}"

    @override
    def get_data_type_confidence(self, df: DataFrame, cols: tuple[str]) -> float:
        return 1 if "email" in cols[0].lower() else 0

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
