from collections.abc import Iterable
from enum import StrEnum
from typing import ClassVar, override

from dataclean.engine import DataFrame, DataType
from dataclean.types import checked

from .cleaner import Cleaner


@checked
class BoolCleaner(Cleaner):
    class Format(StrEnum):
        TRUEFALSE = "truefalse"  # Returns Python boolean primitives: True / False
        TRUEFALSE_STR = (
            "truefalse_str"  # Returns Python boolean primitives: "True" / "False"
        )
        TF = "tf"  # Returns Python boolean primitives: T / F
        BINARY = "binary"  # Returns structured string flags: "1" / "0"
        YESNO = "yesno"  # Returns standardized YES NO representations: "YES" / "NO"
        YN = "yn"  # Returns standardized Y N representations: "Y" / "N"

    class Case(StrEnum):
        UPPER = "upper"  # Returns uppercase values: "YES" / "NO"
        LOWER = "lower"  # Returns lowercase values: "yes" / "no"
        PASCAL = "pascal"  # Returns PascalCase values: "Yes" / "No"

    # Static global evaluation mapping table for strict runtime lookups
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
    _out_case: Case
    _truthy_values: frozenset[str]
    _falsy_values: frozenset[str]
    _true_out: str | bool
    _false_out: str | bool
    _match_prefixes: frozenset[str]
    _match_suffixes: frozenset[str]

    def __init__(
        self,
        truthy_values: Iterable[str] = DEFAULT_TRUTHY_VALUES,
        falsy_values: Iterable[str] = DEFAULT_FALSY_VALUES,
        extra_truthy_values: Iterable[str] = (),
        extra_falsy_values: Iterable[str] = (),
        out_format: Format = Format.TRUEFALSE,
        out_case: Case = Case.PASCAL,
        match_prefixes: Iterable[str] = DEFAULT_MATCH_PREFIXES,
        match_suffixes: Iterable[str] = DEFAULT_MATCH_SUFFIXES,
        extra_match_prefixes: Iterable[str] = (),
        extra_match_suffixes: Iterable[str] = (),
        tags: tuple[str, ...] = (),
    ):
        self._truthy_values = frozenset(
            v.strip().lower() for v in (*truthy_values, *extra_truthy_values)
        )
        self._falsy_values = frozenset(
            v.strip().lower() for v in (*falsy_values, *extra_falsy_values)
        )
        self._match_prefixes = frozenset(
            v.strip().lower() for v in (*match_prefixes, *extra_match_prefixes)
        )
        self._match_suffixes = frozenset(
            v.strip().lower() for v in (*match_suffixes, *extra_match_suffixes)
        )
        self._out_format = out_format
        self._out_case = out_case

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
            match out_case:
                case BoolCleaner.Case.UPPER:
                    true_out = true_out.upper()
                    false_out = false_out.upper()
                case BoolCleaner.Case.PASCAL:
                    true_out = true_out[0].upper() + true_out[1:]
                    false_out = false_out[0].upper() + false_out[1:]
                case _:
                    raise ValueError(f"Invalid out_case: {out_case}")

        self._true_out = true_out
        self._false_out = false_out

        super().__init__(tags=tags)

    @property
    def truthy_values(self) -> frozenset[str]:
        return self._truthy_values

    @property
    def falsy_values(self) -> frozenset[str]:
        return self._falsy_values

    @property
    def out_format(self) -> Format:
        return self._out_format

    @property
    def out_case(self) -> Case:
        return self._out_case

    @property
    def true_out(self) -> str | bool:
        return self._true_out

    @property
    def false_out(self) -> str | bool:
        return self._false_out

    @property
    def match_prefixes(self) -> frozenset[str]:
        return self._match_prefixes

    @property
    def match_suffixes(self) -> frozenset[str]:
        return self._match_suffixes

    @override
    def _outputs(self) -> Cleaner.OutputSchema:
        dtype = (
            DataType.BOOL
            if self._out_format == BoolCleaner.Format.TRUEFALSE
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

        assert len(v.strip()) > 0, "v must be a non-empty string"
        assert v.strip() == v, "v must not contain leading or trailing whitespace"

        normalized = v.lower()

        if normalized in self._truthy_values:
            return self._true_out

        if normalized in self._falsy_values:
            return self._false_out

        return None

    @override
    def match_score(self, df: DataFrame, cols: tuple[str, ...]) -> float:

        assert len(cols) == 1, "cols must be a tuple of length 1"

        col = cols[0].lower()

        if any(col.startswith(prefix) for prefix in self._match_prefixes):
            return Cleaner.MAX_SCORE

        if any(col.endswith(suffix) for suffix in self._match_suffixes):
            return Cleaner.MAX_SCORE

        return Cleaner.MIN_SCORE
