from enum import StrEnum
from typing import Any, override

from dataclean.cleaners.base_cleaner import BaseCleaner
from dataclean.engine.dataframe import DataFrame, DataType


class BoolCleaner(BaseCleaner, frozen=True):
    class Format(StrEnum):
        TRUEFALSE = "truefalse"  # Returns Python boolean primitives: True / False
        BINARY = "binary"  # Returns structured string flags: "1" / "0"
        YESNO = "yesno"  # Returns standardized yes no representations: "Yes" / "No"

    out_format: Format = Format.TRUEFALSE

    # Static global evaluation mapping table for strict runtime lookups
    _TRUTHY_MAPPING: dict[str, dict[Format, Any]] = {
        "true": {Format.TRUEFALSE: True, Format.BINARY: "1", Format.YESNO: "Yes"},
        "1": {Format.TRUEFALSE: True, Format.BINARY: "1", Format.YESNO: "Yes"},
        "yes": {Format.TRUEFALSE: True, Format.BINARY: "1", Format.YESNO: "Yes"},
        "t": {Format.TRUEFALSE: True, Format.BINARY: "1", Format.YESNO: "Yes"},
        "y": {Format.TRUEFALSE: True, Format.BINARY: "1", Format.YESNO: "Yes"},
        "active": {Format.TRUEFALSE: True, Format.BINARY: "1", Format.YESNO: "Yes"},
    }

    _FALSY_MAPPING: dict[str, dict[Format, Any]] = {
        "false": {Format.TRUEFALSE: False, Format.BINARY: "0", Format.YESNO: "No"},
        "0": {Format.TRUEFALSE: False, Format.BINARY: "0", Format.YESNO: "No"},
        "no": {Format.TRUEFALSE: False, Format.BINARY: "0", Format.YESNO: "No"},
        "f": {Format.TRUEFALSE: False, Format.BINARY: "0", Format.YESNO: "No"},
        "n": {Format.TRUEFALSE: False, Format.BINARY: "0", Format.YESNO: "No"},
        "inactive": {Format.TRUEFALSE: False, Format.BINARY: "0", Format.YESNO: "No"},
    }

    @override
    def name(self) -> str:
        return "BoolCleaner"

    @override
    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]:
        # Maps dynamically to 'bool' if native, or 'str' if converting to formatted flags
        return "bool" if self.out_format == BoolCleaner.Format.TRUEFALSE else "str"

    @override
    def clean_value(self, v: str) -> Any | None:
        normalized = v.lower()

        if normalized in self._TRUTHY_MAPPING:
            return self._TRUTHY_MAPPING[normalized][self.out_format]

        if normalized in self._FALSY_MAPPING:
            return self._FALSY_MAPPING[normalized][self.out_format]

        return None

    @override
    def get_data_type_confidence(self, df: DataFrame, cols: tuple[str, ...]) -> float:

        col_name = cols[0].lower()

        if any(
            token in col_name for token in ("is_", "has_", "active", "status", "flag")
        ):
            return 1.0
        return 0.0
