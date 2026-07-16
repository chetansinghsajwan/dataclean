import re
from enum import StrEnum
from typing import override
import phonenumbers

from dataclean.cleaners.base_cleaner import BaseCleaner
from dataclean.engine.dataframe import DataFrame, DataType


class PhoneCleaner(BaseCleaner, frozen=True):
    class Format(StrEnum):
        E164 = "e164"
        INTERNATIONAL = "international"
        NATIONAL = "national"
        RAW_DIGITS = "raw_digits"

    out_format: Format = Format.E164
    default_regions: tuple[str, ...] = ()

    @override
    def name(self) -> str:
        return "PhoneCleaner"

    @override
    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]:
        return "str"

    @override
    def clean_value(self, v: str) -> str | None:
        normalized = v.strip()

        if re.match(r'^\d+(\.\d+)?([eE][+-]?\d+)$', normalized):
            try:
                normalized = str(int(float(normalized)))
            except ValueError:
                pass

        # 🚀 FIX 1: Ensure the execution loop runs at least once, even if default_regions is empty.
        # This allows self-contained E.164 formats (+91...) to be parsed securely.
        regions_to_try = self.default_regions if self.default_regions else (None,)

        for region in regions_to_try:
            try:
                parsed_num = phonenumbers.parse(normalized, region)

                if phonenumbers.is_valid_number(parsed_num):
                    match self.out_format:
                        case PhoneCleaner.Format.E164:
                            return phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.E164)
                        case PhoneCleaner.Format.INTERNATIONAL:
                            return phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                        case PhoneCleaner.Format.NATIONAL:
                            return phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.NATIONAL)
                        case PhoneCleaner.Format.RAW_DIGITS:
                            e164 = phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.E164)
                            return e164.replace("+", "")

            except phonenumbers.NumberParseException:
                continue

        return None

    @override
    def get_data_type_confidence(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        if not cols:
            return 0.0

        col_name = cols[0].lower()
        if any(token in col_name for token in ("phone", "tel", "mobile", "fax", "contact_no")):
            return 1.0

        return 0.0
