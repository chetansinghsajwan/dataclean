"""Boolean cleaner for mapping messy true/false-like values to a canonical format."""

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
    """Cleans boolean-like values into a canonical true/false representation.

    Built on top of ``EnumCleaner``: truthy/falsy input variants are matched
    case-insensitively as exact-match cases, and the resolved value is
    formatted (and cased) according to ``out_format``/``out_case``.

    Attributes:
        DEFAULT_TRUTHY_VALUES: Input strings recognized as "true" by
            default.
        DEFAULT_FALSY_VALUES: Input strings recognized as "false" by
            default.
        DEFAULT_MATCH_PREFIXES: Column-name prefixes used by ``match_score``
            to recognize boolean-like columns (e.g. "is_active").
        DEFAULT_MATCH_SUFFIXES: Column-name suffixes used by ``match_score``
            to recognize boolean-like columns (e.g. "active_flag").
    """

    class Format(StrEnum):
        """Output representations a BoolCleaner can produce."""

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
        """Initialize a BoolCleaner.

        Args:
            truthy_values: Input strings treated as true. Defaults to
                DEFAULT_TRUTHY_VALUES.
            falsy_values: Input strings treated as false. Defaults to
                DEFAULT_FALSY_VALUES.
            extra_truthy_values: Additional strings treated as true,
                appended to truthy_values.
            extra_falsy_values: Additional strings treated as false,
                appended to falsy_values.
            out_format: The output representation to produce. Defaults to
                Format.TRUEFALSE.
            out_case: The text case applied to string output formats.
                Defaults to TextCase.PASCAL.
            match_prefixes: Column-name prefixes used to detect
                boolean-like columns. Defaults to DEFAULT_MATCH_PREFIXES.
            match_suffixes: Column-name suffixes used to detect
                boolean-like columns. Defaults to DEFAULT_MATCH_SUFFIXES.
            extra_match_prefixes: Additional column-name prefixes, appended
                to match_prefixes.
            extra_match_suffixes: Additional column-name suffixes, appended
                to match_suffixes.
            tags: Optional labels distinguishing multiple BoolCleaner
                instances.
        """
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
        """Return the set of input variants recognized as true."""
        matcher = self._cases[self._true_out]
        assert isinstance(matcher, EnumCleaner.ExactMatcher)

        return matcher.variants

    @property
    def falsy_values(self) -> frozenset[str]:
        """Return the set of input variants recognized as false."""
        matcher = self._cases[self._false_out]
        assert isinstance(matcher, EnumCleaner.ExactMatcher)

        return matcher.variants

    @property
    def out_format(self) -> Format:
        """Return the configured output format."""
        return self._out_format

    @property
    def out_case(self) -> TextCase:
        """Return the configured output text case."""
        return self._out_case

    @property
    def true_out(self) -> str | bool:
        """Return the canonical output value used for true."""
        return self._true_out

    @property
    def false_out(self) -> str | bool:
        """Return the canonical output value used for false."""
        return self._false_out

    @property
    def match_prefixes(self) -> frozenset[str]:
        """Return the column-name prefixes used to detect boolean-like columns."""
        return self.cleaner_matching_prefixes

    @property
    def match_suffixes(self) -> frozenset[str]:
        """Return the column-name suffixes used to detect boolean-like columns."""
        return self.cleaner_matching_suffixes

    @override
    def _outputs(self) -> Cleaner.OutputSchema:
        """Return the output schema.

        Uses DataType.BOOL when out_format is Format.TRUEFALSE (native
        booleans), otherwise DataType.STR for the string-formatted output.
        """
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
        """Build the canonical true/false output values and their matcher cases.

        Args:
            out_format: The output representation to produce.
            out_case: The text case applied to string output formats.
            truthy_values: Input strings treated as true.
            falsy_values: Input strings treated as false.
            extra_truthy_values: Additional strings treated as true.
            extra_falsy_values: Additional strings treated as false.

        Returns:
            A tuple of ``(true_out, false_out, cases)`` where ``cases`` is
            the EnumCleaner-style mapping of canonical output value to an
            ExactMatcher over the recognized input variants.

        Raises:
            ValueError: If out_format is not a recognized Format value.
        """

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
