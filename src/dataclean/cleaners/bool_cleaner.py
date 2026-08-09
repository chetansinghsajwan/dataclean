from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, override

from dataclean.cleaners.cleaner import Cleaner
from dataclean.engine.dataframe import DataFrame, DataType
from dataclean.types import checked


@checked
@dataclass
class BoolCleaner(Cleaner):
    class Format(StrEnum):
        TRUEFALSE = "truefalse"  # Returns Python boolean primitives: True / False
        BINARY = "binary"  # Returns structured string flags: "1" / "0"
        YESNO = "yesno"  # Returns standardized yes no representations: "Yes" / "No"

    out_format: Format = Format.TRUEFALSE

    # Static global evaluation mapping table for strict runtime lookups
    _TRUTHY_MAPPING: ClassVar = {
        "true": {Format.TRUEFALSE: True, Format.BINARY: "1", Format.YESNO: "Yes"},
        "1": {Format.TRUEFALSE: True, Format.BINARY: "1", Format.YESNO: "Yes"},
        "yes": {Format.TRUEFALSE: True, Format.BINARY: "1", Format.YESNO: "Yes"},
        "t": {Format.TRUEFALSE: True, Format.BINARY: "1", Format.YESNO: "Yes"},
        "y": {Format.TRUEFALSE: True, Format.BINARY: "1", Format.YESNO: "Yes"},
        "active": {Format.TRUEFALSE: True, Format.BINARY: "1", Format.YESNO: "Yes"},
    }

    _FALSY_MAPPING: ClassVar = {
        "false": {Format.TRUEFALSE: False, Format.BINARY: "0", Format.YESNO: "No"},
        "0": {Format.TRUEFALSE: False, Format.BINARY: "0", Format.YESNO: "No"},
        "no": {Format.TRUEFALSE: False, Format.BINARY: "0", Format.YESNO: "No"},
        "f": {Format.TRUEFALSE: False, Format.BINARY: "0", Format.YESNO: "No"},
        "n": {Format.TRUEFALSE: False, Format.BINARY: "0", Format.YESNO: "No"},
        "inactive": {Format.TRUEFALSE: False, Format.BINARY: "0", Format.YESNO: "No"},
    }

    @override
    def _outputs(self) -> Cleaner.OutputSchema:

        dtype = (
            DataType.BOOL
            if self.out_format == BoolCleaner.Format.TRUEFALSE
            else DataType.STR
        )

        return Cleaner.OutputSchema(
            cols=(
                Cleaner.OutputSchema.Column(
                    name=None,
                    dtype=dtype,
                ),
            )
        )

    @override
    def clean_row(self, v: str) -> str | bool | None:  # type: ignore

        normalized = v.lower()

        if normalized in self._TRUTHY_MAPPING:
            return self._TRUTHY_MAPPING[normalized][self.out_format]

        if normalized in self._FALSY_MAPPING:
            return self._FALSY_MAPPING[normalized][self.out_format]

        return None

    @override
    def match_score(self, df: DataFrame, cols: Iterable[str]) -> float:

        col_name = tuple(cols)[0].lower()

        if any(
            token in col_name for token in ("is_", "has_", "active", "status", "flag")
        ):
            return 1.0
        return 0.0
