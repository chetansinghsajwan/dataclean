from collections.abc import Iterable
from enum import StrEnum
from typing import Any, ClassVar, override

from dataclean.engine import DataType
from dataclean.types import checked
from dataclean.utils.case import TextCase, convert_to_case

from .cleaner import Cleaner
from .enum_cleaner import EnumCleaner


@checked
class BoolCleaner(EnumCleaner):
    class Format(StrEnum):
        TRUEFALSE = "truefalse"  # Returns Python boolean primitives: True / False
        TRUEFALSE_STR = (
            "truefalse_str"  # Returns Python boolean primitives: "True" / "False"
        )
        TF = "tf"  # Returns Python boolean primitives: T / F
        BINARY = "binary"  # Returns structured string flags: "1" / "0"
        YESNO = "yesno"  # Returns standardized YES NO representations: "YES" / "NO"
        YN = "yn"  # Returns standardized Y N representations: "Y" / "N"

    DEFAULT_TRUTHY_VALUES: ClassVar[tuple[str, ...]] = (
        "true",
        "1",
        "yes",
        "t",
        "y",
        "active",
    )
    DEFAULT_FALSY_VALUES: ClassVar[tuple[str, ...]] = (
        "false",
        "0",
        "no",
        "f",
        "n",
        "inactive",
    )
    DEFAULT_MATCH_PREFIXES: ClassVar[tuple[str, ...]] = (
        "is",
        "has",
        "active",
        "status",
        "flag",
    )
    DEFAULT_MATCH_SUFFIXES: ClassVar[tuple[str, ...]] = (
        "active",
        "status",
        "flag",
    )

    _out_format: Format
    _out_case: TextCase
    _true_out: str | bool
    _false_out: str | bool

    def __init__(
        self,
        truthy_values: Iterable[str] = DEFAULT_TRUTHY_VALUES,
        falsy_values: Iterable[str] = DEFAULT_FALSY_VALUES,
        extra_truthy_values: Iterable[str] = (),
        extra_falsy_values: Iterable[str] = (),
        out_format: Format = Format.TRUEFALSE,
        out_case: TextCase = TextCase.PASCAL,
        match_prefixes: Iterable[str] = DEFAULT_MATCH_PREFIXES,
        match_suffixes: Iterable[str] = DEFAULT_MATCH_SUFFIXES,
        extra_match_prefixes: Iterable[str] = (),
        extra_match_suffixes: Iterable[str] = (),
        tags: tuple[str, ...] = (),
    ):
        self._out_format = out_format
        self._out_case = out_case
        self._true_out, self._false_out, cases = self._build_cases(
            out_format=out_format,
            out_case=out_case,
            truthy_values=truthy_values,
            falsy_values=falsy_values,
            extra_truthy_values=extra_truthy_values,
            extra_falsy_values=extra_falsy_values,
        )

        super().__init__(
            cases=cases,
            cleaner_matching_prefixes=(*match_prefixes, *extra_match_prefixes),
            cleaner_matching_suffixes=(*match_suffixes, *extra_match_suffixes),
            tags=tags,
        )

    @property
    def truthy_values(self) -> frozenset[str]:
        matcher = self._cases[self._true_out]
        assert isinstance(matcher, EnumCleaner.ExactMatcher)

        return matcher.variants

    @property
    def falsy_values(self) -> frozenset[str]:
        matcher = self._cases[self._false_out]
        assert isinstance(matcher, EnumCleaner.ExactMatcher)

        return matcher.variants

    @property
    def out_format(self) -> Format:
        return self._out_format

    @property
    def out_case(self) -> TextCase:
        return self._out_case

    @property
    def true_out(self) -> str | bool:
        return self._true_out

    @property
    def false_out(self) -> str | bool:
        return self._false_out

    @property
    def match_prefixes(self) -> frozenset[str]:
        return self.cleaner_matching_prefixes

    @property
    def match_suffixes(self) -> frozenset[str]:
        return self.cleaner_matching_suffixes

    @override
    def _outputs(self) -> Cleaner.OutputSchema:
        dtype = (
            DataType.BOOL
            if self._out_format == BoolCleaner.Format.TRUEFALSE
            else DataType.STR
        )
        return Cleaner.OutputSchema(
            cols=(Cleaner.OutputSchema.Column(name=None, dtype=dtype),)
        )

    @staticmethod
    def _build_cases(
        out_format: Format,
        out_case: TextCase,
        truthy_values: Iterable[str],
        falsy_values: Iterable[str],
        extra_truthy_values: Iterable[str] = (),
        extra_falsy_values: Iterable[str] = (),
    ) -> tuple[str | bool, str | bool, Any]:

        true_out: str | bool
        false_out: str | bool

        match out_format:
            case BoolCleaner.Format.TRUEFALSE:
                true_out = True
                false_out = False
            case BoolCleaner.Format.TRUEFALSE_STR:
                true_out = "True"
                false_out = "False"
            case BoolCleaner.Format.TF:
                true_out = "T"
                false_out = "F"
            case BoolCleaner.Format.BINARY:
                true_out = "1"
                false_out = "0"
            case BoolCleaner.Format.YESNO:
                true_out = "Yes"
                false_out = "No"
            case _:
                raise ValueError(f"Invalid out_format: {out_format}")

        if isinstance(true_out, str) and isinstance(false_out, str):
            true_out = convert_to_case(true_out, out_case)
            false_out = convert_to_case(false_out, out_case)

        cases: dict[str | bool, EnumCleaner.ExactMatcher] = {
            true_out: EnumCleaner.ExactMatcher(
                variants=(*truthy_values, *extra_truthy_values),
                case_sensitive=False,
            ),
            false_out: EnumCleaner.ExactMatcher(
                variants=(*falsy_values, *extra_falsy_values),
                case_sensitive=False,
            ),
        }

        return true_out, false_out, cases
