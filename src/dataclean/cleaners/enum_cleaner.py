"""Enum cleaner for mapping messy categorical values to canonical labels."""

import logging
import re
from collections.abc import Iterable, Mapping
from typing import Protocol, cast, override, runtime_checkable

from rapidfuzz import fuzz

from dataclean.engine.dataframe import Aggregators, DataFrame
from dataclean.types import checked

from .cleaner import Cleaner

_logger = logging.getLogger(__name__)


@runtime_checkable
class EnumCleanerMatcher(Protocol):
    """Callable protocol for predicates that decide whether a value matches a case."""

    def __call__(self, v: str) -> bool: ...


@checked
class EnumCleaner(Cleaner):
    """Maps messy categorical string values to canonical enum-like labels.

    Each canonical output value ("case") is associated with one or more
    matchers (exact, regex, fuzzy, or a combination). Cleaning a row tries
    each case's matcher in turn and returns the name of the first case whose
    matcher accepts the value, or None if no case matches.

    ``match_score`` additionally supports fast column-name heuristics
    (matching prefixes/suffixes/words) before falling back to a
    data-sampling pass that checks what fraction of a column's distinct
    values are matched by any configured case.
    """

    @checked
    class CombinedMatcher:
        """Matcher that accepts a value if any of its sub-matchers accept it.

        Attributes:
            matchers: The sub-matchers to try, in order.
        """

        matchers: list[EnumCleanerMatcher]

        def __init__(self, matchers: Iterable[EnumCleanerMatcher]):
            self.matchers = list(matchers)

        def __call__(self, v: str) -> bool:
            """Return True if any sub-matcher accepts ``v``."""
            return any(matcher(v) for matcher in self.matchers)

    @checked
    class ExactMatcher:
        """Matcher that accepts a value if it exactly equals one of a set of variants.

        Attributes:
            variants: The accepted literal values.
            case_sensitive: Whether comparison is case-sensitive.
        """

        variants: frozenset[str]
        case_sensitive: bool

        def __init__(self, variants: Iterable[str], case_sensitive: bool = True):
            """Build the matcher from a set of accepted literal variants.

            Args:
                variants: The accepted literal values.
                case_sensitive: If False, both ``variants`` and matched
                    values are lowercased before comparison.
            """
            self.variants = (
                frozenset(variants)
                if case_sensitive
                else frozenset(v.lower() for v in variants)
            )
            self.case_sensitive = case_sensitive

        def __call__(self, v: str) -> bool:
            """Return True if ``v`` exactly equals one of ``variants``."""
            if not self.case_sensitive:
                v = v.lower()

            return v in self.variants

    @checked
    class RegexMatcher:
        """Matcher that accepts a value if it fully matches a regex pattern.

        Attributes:
            pattern: The compiled pattern the value must fully match.
            case_sensitive: Whether the match is case-sensitive.
        """

        pattern: re.Pattern
        case_sensitive: bool

        def __init__(self, pattern: str | re.Pattern, case_sensitive: bool = True):
            """Build the matcher from a pattern string or a precompiled pattern.

            Args:
                pattern: A regex string (compiled here with
                    ``re.IGNORECASE`` unless the pattern is already a
                    compiled ``re.Pattern``, in which case it is used as-is)
                    or a precompiled ``re.Pattern``.
                case_sensitive: Whether matched values are lowercased before
                    comparison. Note this is independent of any
                    ``re.IGNORECASE`` flag already baked into a precompiled
                    pattern.
            """
            self.pattern = (
                re.compile(pattern, re.IGNORECASE if isinstance(pattern, str) else 0)
                if isinstance(pattern, str)
                else pattern
            )
            self.case_sensitive = case_sensitive

        def __call__(self, v: str) -> bool:
            """Return True if ``v`` fully matches ``pattern``."""
            if not self.case_sensitive:
                v = v.lower()

            return bool(self.pattern.fullmatch(v))

    @checked
    class FuzzyMatcher:
        """Matcher that accepts a value if it is fuzzy-similar to a set of variants.

        Similarity is computed with ``rapidfuzz.fuzz.ratio``, which scores
        0-100.

        Attributes:
            variants: The reference values to compare against.
            threshold: Minimum similarity ratio, on a 0.0-1.0 scale, required
                to accept a value.
            case_sensitive: Whether comparison is case-sensitive.
        """

        variants: frozenset[str]
        threshold: float
        case_sensitive: bool

        def __init__(
            self,
            variants: Iterable[str],
            threshold: float = 0.9,
            case_sensitive: bool = True,
        ):
            """Build the matcher from reference variants and a similarity threshold.

            Args:
                variants: The reference values to compare against.
                threshold: Minimum similarity ratio (0.0-1.0) required to
                    accept a value.
                case_sensitive: If False, both ``variants`` and matched
                    values are lowercased before comparison.

            Raises:
                ValueError: If ``threshold`` is not between 0.0 and 1.0.
            """
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
            """Return True if ``v`` is similar enough to any variant."""
            if not self.case_sensitive:
                v = v.lower()

            return any(
                fuzz.ratio(v, variant) >= self.threshold * 100
                for variant in self.variants
            )

    CaseKey = str | bool | int | float

    _cases: dict[CaseKey, EnumCleanerMatcher]
    _cleaner_matching_prefixes: frozenset[str]
    _cleaner_matching_suffixes: frozenset[str]
    _cleaner_matching_words: frozenset[str]

    def __init__(
        self,
        cases: Iterable[str]
        | Mapping[CaseKey, str | Iterable[str] | EnumCleanerMatcher],
        cleaner_matching_prefixes: Iterable[str] = (),
        cleaner_matching_suffixes: Iterable[str] = (),
        cleaner_matching_words: Iterable[str] = (),
        tags: tuple[str, ...] = (),
    ):
        """Build the cleaner from a set of canonical cases and their matchers.

        Args:
            cases: Either an iterable of canonical string values (each
                matched exactly against itself), or a mapping from a
                canonical case key to a matcher spec: a single string
                (exact match), an iterable of strings (exact match against
                any of them), or an ``EnumCleanerMatcher`` callable.
            cleaner_matching_prefixes: Column-name prefixes that, if matched,
                make ``match_score`` return the maximum score immediately.
            cleaner_matching_suffixes: Column-name suffixes that, if matched,
                make ``match_score`` return the maximum score immediately.
            cleaner_matching_words: Substrings that, if found anywhere in
                the column name, make ``match_score`` return the maximum
                score immediately.
            tags: Tags identifying this cleaner instance, passed through to
                the base ``Cleaner``.
        """
        _logger.info("Compiling cases...")
        self._cases = self._compile_cases(cases)

        self._cleaner_matching_prefixes = frozenset(cleaner_matching_prefixes)
        self._cleaner_matching_suffixes = frozenset(cleaner_matching_suffixes)
        self._cleaner_matching_words = frozenset(cleaner_matching_words)

        super().__init__(tags=tags)

    @property
    def cases(self) -> dict[CaseKey, EnumCleanerMatcher]:
        """Return the compiled mapping of canonical case key to matcher."""
        return self._cases

    @property
    def cleaner_matching_prefixes(self) -> frozenset[str]:
        """Return the column-name prefixes that force a max match score."""
        return self._cleaner_matching_prefixes

    @property
    def cleaner_matching_suffixes(self) -> frozenset[str]:
        """Return the column-name suffixes that force a max match score."""
        return self._cleaner_matching_suffixes

    @property
    def cleaner_matching_words(self) -> frozenset[str]:
        """Return the column-name substrings that force a max match score."""
        return self._cleaner_matching_words

    @staticmethod
    def _compile_cases(
        cases: Iterable[str]
        | Mapping[CaseKey, str | Iterable[str] | EnumCleanerMatcher],
    ) -> dict[CaseKey, EnumCleanerMatcher]:
        """Normalize the ``cases`` constructor argument into matcher callables.

        Args:
            cases: Either an iterable of canonical values (each becomes an
                ``ExactMatcher`` matching itself), or a mapping from a
                canonical case key to a matcher spec (string, iterable of
                strings, or an ``EnumCleanerMatcher`` callable).

        Returns:
            A mapping from canonical case key to a callable matcher.

        Raises:
            TypeError: If a mapping value is not a string, an iterable of
                strings, or a callable matcher.
        """
        Matcher = EnumCleanerMatcher
        compiled_cases: dict[EnumCleaner.CaseKey, Matcher] = {}

        if isinstance(cases, Mapping):
            cases = cast(Mapping[EnumCleaner.CaseKey, Matcher], cases)

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
    def clean_row(self, v: str) -> CaseKey | None:  # type: ignore
        """Return the canonical case key whose matcher accepts ``v``.

        Cases are tried in insertion order; the first matcher that accepts
        ``v`` wins.

        Args:
            v: The raw value to classify.

        Returns:
            The canonical case key of the first matching case, or None if
            no case matches.
        """

        assert len(v.strip()) > 0, "v must be a non-empty string"
        assert v.strip() == v, "v must not contain leading or trailing whitespace"

        for name, matcher in self._cases.items():
            if matcher(v):
                return name

        return None

    @override
    def match_score(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        """Score confidence that this cleaner's cases apply to ``cols[0]``.

        First checks the fast column-name heuristics
        (``cleaner_matching_prefixes``/``suffixes``/``words``), returning
        the maximum score immediately on any hit. Otherwise, samples up to
        the 100 most frequent distinct non-null values of the column and
        returns the fraction of their occurrences that are accepted by some
        configured case matcher.

        Args:
            df: The dataframe to sample values from.
            cols: A single-element tuple naming the candidate column.

        Returns:
            A confidence score between 0.0 and 1.0.
        """

        assert len(cols) == 1, "cols must be a tuple of length 1"

        logger = _logger.getChild("match_score")

        col = cols[0].lower()
        logger.debug("col: %s", col)

        logger.debug("cleaner_matching_prefixes: %s", self._cleaner_matching_prefixes)
        logger.debug("cleaner_matching_suffixes: %s", self._cleaner_matching_suffixes)
        logger.debug("cleaner_matching_words: %s", self._cleaner_matching_words)

        for prefix in self._cleaner_matching_prefixes:
            if col.startswith(prefix):
                logger.debug("Matched prefix: %s", prefix)
                return Cleaner.MAX_SCORE

        for suffix in self._cleaner_matching_suffixes:
            if col.endswith(suffix):
                logger.debug("Matched suffix: %s", suffix)
                return Cleaner.MAX_SCORE

        for word in self._cleaner_matching_words:
            if word in col:
                logger.debug("Matched word: %s", word)
                return Cleaner.MAX_SCORE

        logger.debug("Matching with values...")

        rows = (
            df.select(cols[0])
            .strip()
            .nullif()
            .filter_null()
            .group_by([cols[0]])
            .agg(Aggregators.count)
            .order_by(cols[0], desc=True)
            .limit(100)
            .collect()
        )

        total_count = 0
        match_count = 0

        rows_len = len(rows)
        rows_len_width = len(str(rows_len))

        for i, (v_in, count_in) in enumerate(rows, start=1):
            logger.debug(
                "[%0*d/%d] Checking %s (%s)",
                rows_len_width,
                i,
                rows_len,
                v_in,
                count_in,
            )

            assert count_in is not None, "count must be a parseable int"
            count = int(count_in)

            v = str(v_in)

            total_count += count

            for _, matcher in self._cases.items():
                if matcher(v):
                    match_count += count
                    break

        match_ratio = match_count / total_count if total_count > 0.0 else 0.0
        return match_ratio
