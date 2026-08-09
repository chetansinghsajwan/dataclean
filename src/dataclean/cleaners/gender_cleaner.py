from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, override

from dataclean.cleaners.cleaner import Cleaner
from dataclean.engine.dataframe import DataFrame
from dataclean.types import checked


@checked
@dataclass
class GenderCleaner(Cleaner):
    class Format(StrEnum):
        FULL = "full"  # "Male" / "Female" / "Other"
        CHAR = "char"  # "M" / "F" / "O"
        BINARY = "binary"  # "1" / "0" / "-1"

    out_format: Format = Format.FULL

    # Shared static mapping configuration matrix
    _MAPPING: ClassVar = {
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
    def clean_row(self, v: str) -> str | None:  # type: ignore

        match_details = self._MAPPING.get(v.lower())

        if match_details is None:
            return None

        return match_details[self.out_format]

    @override
    def match_score(self, df: DataFrame, cols: Iterable[str]) -> float:
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0

        col_name = cols_tuple[0].lower()
        if "gender" in col_name or "sex" in col_name:
            return 1.0

        return 0.0
