"""Cleaner for normalizing messy gender/sex values to a canonical label."""

import logging
from collections.abc import Iterable, Mapping
from enum import StrEnum

from dataclean.types import checked
from dataclean.utils.case import TextCase, convert_to_case

from .enum_cleaner import EnumCleaner, EnumCleanerMatcher

_logger = logging.getLogger(__name__)


@checked
class GenderCleaner(EnumCleaner):
    """Maps messy gender/sex values (e.g. "M", "woman", "-1") to a canonical label.

    This is a thin, pre-configured wrapper around ``EnumCleaner``: it builds
    an ``ExactMatcher`` (case-insensitive) per gender case from the
    ``genders``/``extra_genders`` variant lists, renders the canonical case
    keys in the requested ``out_format`` and text ``case``, and defaults the
    column-name matching words to ``["gender", "sex"]``.
    """

    class Format(StrEnum):
        """Output label styles for cleaned gender values."""

        FULL = "full"  # "Male" / "Female" / "Other"
        CHAR = "char"  # "M" / "F" / "O"
        BINARY = "binary"  # "1" / "0" / "-1"

    out_format: Format = Format.FULL

    _FORMATS = {
        "male": {Format.FULL: "male", Format.CHAR: "m", Format.BINARY: "1"},
        "female": {Format.FULL: "female", Format.CHAR: "f", Format.BINARY: "0"},
        "other": {Format.FULL: "other", Format.CHAR: "o", Format.BINARY: "-1"},
    }

    DEFAULT_CLEANER_MATCHING_WORDS = ["gender", "sex"]
    DEFAULT_FUZZY_THRESHOLD = 0.9

    GENDERS = {
        "male": ["male", "man", "m", "boy", "1"],
        "female": ["female", "woman", "f", "girl", "0"],
        "other": ["other", "non-binary", "prefer not to say", "o", "-1"],
    }

    def __init__(
        self,
        format: Format = Format.FULL,
        case: TextCase = TextCase.PASCAL,
        genders: Mapping[str, Iterable[str]] = GENDERS,
        extra_genders: Mapping[str, Iterable[str]] = {},
        tags: tuple[str, ...] = (),
        fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
        cleaner_matching_words: Iterable[str] = DEFAULT_CLEANER_MATCHING_WORDS,
    ):
        """Build the cleaner's gender cases from variant lists.

        Args:
            format: The output label style ("full", "char", or "binary").
            case: The text case to render the ``full``/``char`` canonical
                labels in (ignored for ``binary``, whose labels are numeric
                strings).
            genders: Mapping from canonical gender name to its accepted
                input variants.
            extra_genders: Additional gender name -> variants entries merged
                on top of ``genders`` (overriding entries with the same
                key).
            tags: Tags identifying this cleaner instance, passed through to
                the base ``EnumCleaner``.
            fuzzy_threshold: Currently unused; reserved for enabling fuzzy
                matching of variants.
            cleaner_matching_words: Column-name substrings that make
                ``match_score`` return the maximum score immediately.
        """
        self._match_words = frozenset(cleaner_matching_words)

        _logger.info("Building cases for gender cleaner...")
        cases = self._build_cases(
            genders=genders,
            extra_genders=extra_genders,
            fuzzy_threshold=fuzzy_threshold,
            format=format,
            case=case,
        )

        super().__init__(
            cases=cases,
            cleaner_matching_words=GenderCleaner.DEFAULT_CLEANER_MATCHING_WORDS,
            tags=tags,
        )

    def _build_cases(
        self,
        genders: Mapping[str, Iterable[str]],
        extra_genders: Mapping[str, Iterable[str]],
        fuzzy_threshold: float,
        format: Format,
        case: TextCase,
    ) -> dict[str, EnumCleanerMatcher]:
        """Build one case-insensitive exact matcher per canonical gender.

        Merges ``genders`` and ``extra_genders``, renders each canonical key
        into the requested output ``format`` (looking it up in
        ``_FORMATS`` when it is one of the known "male"/"female"/"other"
        keys, otherwise leaving it unchanged), applies the requested text
        ``case`` (skipped for ``BINARY`` format), and wraps each entry's
        variants in an ``ExactMatcher``.

        Args:
            genders: Mapping from canonical gender name to accepted variants.
            extra_genders: Additional entries merged on top of ``genders``.
            fuzzy_threshold: Currently unused (see ``__init__``).
            format: The output label style used to render canonical keys.
            case: The text case applied to non-binary canonical keys.

        Returns:
            Mapping from rendered canonical gender label to its matcher.
        """
        all_genders = {**genders, **extra_genders}

        all_genders = {
            (
                GenderCleaner._FORMATS[n][format]
                if n in GenderCleaner._FORMATS.keys()
                else n
            ): variants
            for n, variants in all_genders.items()
        }

        if format != GenderCleaner.Format.BINARY:
            all_genders = {
                convert_to_case(n, case): variants
                for n, variants in all_genders.items()
            }

        cases: dict[str, EnumCleanerMatcher] = {
            gender: EnumCleaner.ExactMatcher(
                variants=variants,
                case_sensitive=False,
                # threshold=fuzzy_threshold,
            )
            for gender, variants in all_genders.items()
        }

        return cases
