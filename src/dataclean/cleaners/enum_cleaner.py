"""Enum cleaner for mapping messy categorical values to canonical labels."""

import logging
import re
from collections.abc import Iterable, Mapping
from typing import Protocol, cast, override, runtime_checkable

from rapidfuzz import fuzz

from dataclean.engine.dataframe import DataFrame
from dataclean.types import checked

from .cleaner import Cleaner

_logger = logging.getLogger(__name__)


@runtime_checkable
class EnumCleanerMatcher(Protocol):
    def __call__(self, v: str) -> bool: ...


@checked
class EnumCleaner(Cleaner):
    @checked
    class CombinedMatcher:
        matchers: list[EnumCleanerMatcher]

        def __init__(self, matchers: Iterable[EnumCleanerMatcher]):
            self.matchers = list(matchers)

        def __call__(self, v: str) -> bool:
            return any(matcher(v) for matcher in self.matchers)

    @checked
    class ExactMatcher:
        variants: frozenset[str]
        case_sensitive: bool

        def __init__(self, variants: Iterable[str], case_sensitive: bool = True):
            self.variants = (
                frozenset(variants)
                if case_sensitive
                else frozenset(v.lower() for v in variants)
            )
            self.case_sensitive = case_sensitive

        def __call__(self, v: str) -> bool:
            if not self.case_sensitive:
                v = v.lower()

            return v in self.variants

    @checked
    class RegexMatcher:
        pattern: re.Pattern
        case_sensitive: bool

        def __init__(self, pattern: str | re.Pattern, case_sensitive: bool = True):
            self.pattern = (
                re.compile(pattern, re.IGNORECASE if isinstance(pattern, str) else 0)
                if isinstance(pattern, str)
                else pattern
            )
            self.case_sensitive = case_sensitive

        def __call__(self, v: str) -> bool:
            if not self.case_sensitive:
                v = v.lower()

            return bool(self.pattern.fullmatch(v))

    @checked
    class FuzzyMatcher:
        variants: frozenset[str]
        threshold: float
        case_sensitive: bool

        def __init__(
            self,
            variants: Iterable[str],
            threshold: float = 0.9,
            case_sensitive: bool = True,
        ):
            if threshold < 0.0 or threshold > 1.0:
                raise ValueError("threshold must be between 0.0 and 1.0")

            self.variants = (
                frozenset(variants)
                if case_sensitive
                else frozenset(v.lower() for v in variants)
            )
            self.threshold = threshold
            self.case_sensitive = case_sensitive

        def __call__(self, v: str) -> bool:
            if not self.case_sensitive:
                v = v.lower()

            return any(
                fuzz.ratio(v, variant) >= self.threshold * 100
                for variant in self.variants
            )

    _cases: dict[str, EnumCleanerMatcher]
    _cleaner_matching_prefixes: frozenset[str]
    _cleaner_matching_suffixes: frozenset[str]
    _cleaner_matching_words: frozenset[str]

    def __init__(
        self,
        cases: Iterable[str] | Mapping[str, str | Iterable[str] | EnumCleanerMatcher],
        cleaner_matching_prefixes: Iterable[str] = (),
        cleaner_matching_suffixes: Iterable[str] = (),
        cleaner_matching_words: Iterable[str] = (),
        tags: tuple[str, ...] = (),
    ):
        _logger.info("Compiling cases...")
        self._cases = self._compile_cases(cases)

        self._cleaner_matching_prefixes = frozenset(cleaner_matching_prefixes)
        self._cleaner_matching_suffixes = frozenset(cleaner_matching_suffixes)
        self._cleaner_matching_words = frozenset(cleaner_matching_words)

        super().__init__(tags=tags)

    @property
    def cases(self) -> dict[str, EnumCleanerMatcher]:
        return self._cases

    @property
    def cleaner_matching_prefixes(self) -> frozenset[str]:
        return self._cleaner_matching_prefixes

    @property
    def cleaner_matching_suffixes(self) -> frozenset[str]:
        return self._cleaner_matching_suffixes

    @property
    def cleaner_matching_words(self) -> frozenset[str]:
        return self._cleaner_matching_words

    @staticmethod
    def _compile_cases(
        cases: Iterable[str] | Mapping[str, str | Iterable[str] | EnumCleanerMatcher],
    ) -> dict[str, EnumCleanerMatcher]:
        Matcher = EnumCleanerMatcher
        compiled_cases: dict[str, Matcher] = {}

        if isinstance(cases, Mapping):
            cases = cast(Mapping[str, Matcher], cases)

            matcher: Matcher
            for case, matcher in cases.items():
                if isinstance(matcher, str):
                    matcher = EnumCleaner.ExactMatcher(variants=[matcher])

                elif isinstance(matcher, Iterable):
                    matcher = EnumCleaner.ExactMatcher(
                        variants=cast(Iterable[str], matcher)
                    )
                elif callable(matcher):
                    matcher = cast(Matcher, matcher)
                else:
                    raise TypeError(f"Invalid matcher type: {type(matcher)}")

                compiled_cases[case] = matcher

            return compiled_cases

        for item in cases:
            compiled_cases[item] = EnumCleaner.ExactMatcher(variants={item})

        return compiled_cases

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore

        assert len(v.strip()) > 0, "v must be a non-empty string"
        assert v.strip() == v, "v must not contain leading or trailing whitespace"

        for name, matcher in self._cases.items():
            if matcher(v):
                return name

        return None

    @override
    def match_score(self, df: DataFrame, cols: tuple[str, ...]) -> float:

        assert len(cols) == 1, "cols must be a tuple of length 1"

        col = cols[0].lower()

        if any(col.startswith(prefix) for prefix in self._cleaner_matching_prefixes):
            return Cleaner.MAX_SCORE

        if any(col.endswith(suffix) for suffix in self._cleaner_matching_suffixes):
            return Cleaner.MAX_SCORE

        if any(w in col for w in self._cleaner_matching_words):
            return Cleaner.MAX_SCORE

        return Cleaner.MIN_SCORE
