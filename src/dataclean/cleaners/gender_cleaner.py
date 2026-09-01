import logging
from collections.abc import Iterable, Mapping
from enum import StrEnum

from dataclean.types import checked

from .enum_cleaner import EnumCleaner

_logger = logging.getLogger(__name__)


@checked
class GenderCleaner(EnumCleaner):
    class Format(StrEnum):
        FULL = "full"  # "Male" / "Female" / "Other"
        CHAR = "char"  # "M" / "F" / "O"
        BINARY = "binary"  # "1" / "0" / "-1"

    out_format: Format = Format.FULL

    DEFAULT_CLEANER_MATCHING_WORDS = ["gender", "sex"]
    DEFAULT_FUZZY_THRESHOLD = 0.9

    GENDERS = {
        "male": ["male", "man", "m", "boy", "1"],
        "female": ["female", "woman", "f", "girl", "0"],
        "other": ["other", "non-binary", "prefer not to say", "o", "-1"],
    }

    def __init__(
        self,
        genders: Mapping[str, Iterable[str]] = GENDERS,
        extra_genders: Mapping[str, Iterable[str]] = {},
        tags: tuple[str, ...] = (),
        fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
        cleaner_matching_words: Iterable[str] = DEFAULT_CLEANER_MATCHING_WORDS,
    ):
        self._match_words = frozenset(cleaner_matching_words)

        _logger.info("Building cases for gender cleaner...")
        cases = self._build_cases(genders, extra_genders, fuzzy_threshold)

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
    ) -> dict[str, EnumCleaner.Matcher]:
        all_genders = {**genders, **extra_genders}

        cases: dict[str, EnumCleaner.Matcher] = {
            gender: EnumCleaner.FuzzyMatcher(
                variants=variants,
                case_sensitive=False,
                threshold=fuzzy_threshold,
            )
            for gender, variants in all_genders.items()
        }

        return cases
