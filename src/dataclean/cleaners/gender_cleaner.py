"""Cleaner for normalizing messy gender/sex values to a canonical label."""

import logging
from collections.abc import Iterable, Mapping
from enum import StrEnum
from typing import override

from dataclean.engine.dataframe import DataType
from dataclean.types import checked
from dataclean.utils.case import TextCase, convert_to_case

from .cleaner import Cleaner
from .enum_cleaner import EnumCleaner, EnumCleanerMatcher

_logger = logging.getLogger(__name__)


@checked
class GenderCleaner(EnumCleaner):
    """Maps messy gender/sex values (e.g. "M", "woman", "Ms", "x") to a canonical label.

    This is a thin, pre-configured wrapper around ``EnumCleaner``: it builds
    a case-insensitive matcher per gender case from the
    ``genders``/``extra_genders`` variant lists, renders the canonical case
    keys in the requested ``out_format`` and text ``case``, and defaults the
    column-name matching words to ``["gender", "sex"]``.

    Values that say nothing about gender ("unknown", "U", "not specified",
    "prefer not to say", ``0`` and ``9`` of ISO 5218) are not variants of any
    case, so they become None.
    """

    class Format(StrEnum):
        """Output label styles for cleaned gender values."""

        FULL = "full"  # "Male" / "Female" / "Other"
        CHAR = "char"  # "M" / "F" / "O"
        BINARY = "binary"  # 1 / 0 / -1, as integers

    out_format: Format = Format.FULL

    _FORMATS = {
        "male": {Format.FULL: "male", Format.CHAR: "m", Format.BINARY: 1},
        "female": {Format.FULL: "female", Format.CHAR: "f", Format.BINARY: 0},
        "other": {Format.FULL: "other", Format.CHAR: "o", Format.BINARY: -1},
    }

    DEFAULT_CLEANER_MATCHING_WORDS = ["gender", "sex"]

    # 0.83 lets "mal", "femal" and "femlae" match while "male" and "female"
    # (similarity 0.80) never match each other.
    DEFAULT_FUZZY_THRESHOLD = 0.83

    # "1" and "2" are the male and female codes of ISO 5218. Its "0" (not known)
    # and "9" (not applicable) are left out on purpose so they become None.
    GENDERS: Mapping[str, tuple[str, ...]] = {
        "male": (
            "male",
            "man",
            "m",
            "boy",
            "gent",
            "gents",
            "mr",
            "mister",
            "sir",
            "he",
            "1",
        ),
        "female": (
            "female",
            "woman",
            "f",
            "girl",
            "lady",
            "ladies",
            "mrs",
            "ms",
            "miss",
            "madam",
            "she",
            "2",
        ),
        "other": (
            "other",
            "o",
            "x",
            "non-binary",
            "non binary",
            "nonbinary",
            "nb",
            "transgender",
            "trans",
            "tg",
            "intersex",
            "genderqueer",
            "-1",
        ),
    }

    # Variants that also match when they are slightly misspelled. Short ones
    # are left out: one wrong letter in "m" or "tg" changes the meaning.
    _FUZZY_VARIANTS: Mapping[str, tuple[str, ...]] = {
        "male": ("male",),
        "female": ("female", "woman"),
        "other": (
            "non-binary",
            "nonbinary",
            "transgender",
            "intersex",
            "genderqueer",
        ),
    }

    def __init__(
        self,
        format: Format = Format.FULL,
        case: TextCase = TextCase.PASCAL,
        genders: Mapping[str, Iterable[str]] | None = None,
        extra_genders: Mapping[str, Iterable[str]] | None = None,
        tags: tuple[str, ...] = (),
        fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
        cleaner_matching_words: Iterable[str] = DEFAULT_CLEANER_MATCHING_WORDS,
    ):
        """Build the cleaner's gender cases from variant lists.

        Args:
            format: The output label style ("full", "char", or "binary").
                ``binary`` gives the integers 1, 0 and -1 and an integer column.
            case: The text case to render the ``full``/``char`` canonical
                labels in (ignored for ``binary``).
            genders: Mapping from canonical gender name to its accepted
                input variants. Defaults to ``GENDERS``.
            extra_genders: Additional gender name -> variants entries merged
                on top of ``genders`` (overriding entries with the same
                key).
            tags: Tags identifying this cleaner instance, passed through to
                the base ``EnumCleaner``.
            fuzzy_threshold: Similarity (0.0 to 1.0) at which a misspelled long
                variant, such as "femal", still matches. Use 1.0 to turn
                fuzzy matching off.
            cleaner_matching_words: Column-name substrings that make
                ``match_score`` return the maximum score immediately.
        """
        self._format = format

        _logger.info("Building cases for gender cleaner...")
        cases = self._build_cases(
            genders=self.GENDERS if genders is None else genders,
            extra_genders={} if extra_genders is None else extra_genders,
            fuzzy_threshold=fuzzy_threshold,
            format=format,
            case=case,
        )

        super().__init__(
            cases=cases,
            cleaner_matching_words=cleaner_matching_words,
            tags=tags,
        )

    @override
    def _outputs(self) -> Cleaner.OutputSchema:
        """Return the output schema: an integer column for ``binary``, else strings."""
        dtype = DataType.INT if self._format == self.Format.BINARY else DataType.STR
        return Cleaner.OutputSchema(
            cols=(Cleaner.OutputSchema.Column(name=None, dtype=dtype),)
        )

    @staticmethod
    def _build_cases(
        genders: Mapping[str, Iterable[str]],
        extra_genders: Mapping[str, Iterable[str]],
        fuzzy_threshold: float,
        format: Format,
        case: TextCase,
    ) -> dict[EnumCleaner.CaseKey, EnumCleanerMatcher]:
        """Build one case-insensitive matcher per canonical gender.

        Merges ``genders`` and ``extra_genders``, renders each canonical key
        into the requested output ``format`` (looking it up in
        ``_FORMATS`` when it is one of the known "male"/"female"/"other"
        keys, otherwise leaving it unchanged), applies the requested text
        ``case`` (skipped for ``BINARY`` format), and wraps each entry's
        variants in an exact matcher. Known genders also get a fuzzy matcher
        for the misspellings of their long variants.

        Args:
            genders: Mapping from canonical gender name to accepted variants.
            extra_genders: Additional entries merged on top of ``genders``.
            fuzzy_threshold: Similarity needed by the fuzzy matchers.
            format: The output label style used to render canonical keys.
            case: The text case applied to non-binary canonical keys.

        Returns:
            Mapping from rendered canonical gender label to its matcher.
        """
        all_genders = {**genders, **extra_genders}
        cases: dict[EnumCleaner.CaseKey, EnumCleanerMatcher] = {}

        for name, variants in all_genders.items():
            matchers: list[EnumCleanerMatcher] = [
                EnumCleaner.ExactMatcher(variants=variants, case_sensitive=False)
            ]
            fuzzy_variants = GenderCleaner._FUZZY_VARIANTS.get(name, ())
            if fuzzy_variants and fuzzy_threshold < 1.0:
                matchers.append(
                    EnumCleaner.FuzzyMatcher(
                        variants=fuzzy_variants,
                        threshold=fuzzy_threshold,
                        case_sensitive=False,
                    )
                )

            label: EnumCleaner.CaseKey = (
                GenderCleaner._FORMATS[name][format]
                if name in GenderCleaner._FORMATS
                else name
            )
            if format != GenderCleaner.Format.BINARY and isinstance(label, str):
                label = convert_to_case(label, case)

            cases[label] = EnumCleaner.CombinedMatcher(matchers)

        return cases
