from enum import StrEnum
from typing import override

from dataclean.cleaners.base_cleaner import BaseCleaner
from dataclean.engine.dataframe import DataFrame, DataType


class GenderCleaner(BaseCleaner, frozen=True):
    class Format(StrEnum):
        FULL = "full"  # "Male" / "Female" / "Other"
        CHAR = "char"  # "M" / "F" / "O"
        BINARY = "binary"  # "1" / "0" / "-1"

    out_format: Format = Format.FULL

    # Shared static mapping configuration matrix
    _MAPPING: dict[str, dict[Format, str]] = {
        "male": {Format.FULL: "Male", Format.CHAR: "M", Format.BINARY: "1"},
        "m": {Format.FULL: "Male", Format.CHAR: "M", Format.BINARY: "1"},
        "man": {Format.FULL: "Male", Format.CHAR: "M", Format.BINARY: "1"},
        "boy": {Format.FULL: "Male", Format.CHAR: "M", Format.BINARY: "1"},
        "female": {Format.FULL: "Female", Format.CHAR: "F", Format.BINARY: "0"},
        "f": {Format.FULL: "Female", Format.CHAR: "F", Format.BINARY: "0"},
        "woman": {Format.FULL: "Female", Format.CHAR: "F", Format.BINARY: "0"},
        "girl": {Format.FULL: "Female", Format.CHAR: "F", Format.BINARY: "0"},
        "other": {Format.FULL: "Other", Format.CHAR: "O", Format.BINARY: "-1"},
        "o": {Format.FULL: "Other", Format.CHAR: "O", Format.BINARY: "-1"},
        "non-binary": {Format.FULL: "Other", Format.CHAR: "O", Format.BINARY: "-1"},
    }

    @override
    def name(self) -> str:
        return "GenderCleaner"

    @override
    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]:
        return "str"

    @override
    def clean_value(self, v: str) -> str | None:

        match_details = self._MAPPING.get(v.lower())

        if match_details is None:
            return None

        return match_details[self.out_format]

    @override
    def get_data_type_confidence(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        if not cols:
            return 0.0

        col_name = cols[0].lower()
        if "gender" in col_name or "sex" in col_name:
            return 1.0

        return 0.0
