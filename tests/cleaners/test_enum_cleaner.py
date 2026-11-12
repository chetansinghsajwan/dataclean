"""Tests for EnumCleaner: column scoring, case compilation and the matcher types."""

from unittest.mock import MagicMock

import pytest

from dataclean.cleaners.enum_cleaner import EnumCleaner
from dataclean.engine.dataframe import DataFrame

# ==============================================================================
# 1. CORE METADATA & MATCH SCORE TESTS
# ==============================================================================


def test_enum_cleaner_metadata():
    """A freshly built cleaner should introduce itself as EnumCleaner. The pipeline
    relies on that name to tell cleaners apart in its reports."""
    cleaner = EnumCleaner(cases=["a", "b"])
    assert cleaner.name == "EnumCleaner"


def _mock_df_with_value_counts(value_counts):
    """Builds a mocked DataFrame whose fluent chain used by ``match_score``'s
    value-based auto matching resolves ``.collect()`` to the given
    ``(value, count)`` rows, bypassing any real dataframe engine.
    """
    mock_df = MagicMock(spec=DataFrame)
    chain = mock_df.select.return_value.strip.return_value.nullif.return_value.filter_null.return_value.group_by.return_value.agg.return_value.order_by.return_value.limit.return_value
    chain.collect.return_value = value_counts
    return mock_df


@pytest.mark.parametrize(
    "col_name, prefixes, suffixes, words, expected",
    [
        ("status_code", ("status",), (), (), EnumCleaner.MAX_SCORE),
        ("order_status", (), ("status",), (), EnumCleaner.MAX_SCORE),
        ("user_category", (), (), ("category",), EnumCleaner.MAX_SCORE),
        ("first_name", ("status",), ("status",), ("category",), EnumCleaner.MIN_SCORE),
    ],
)
def test_match_score_by_column_name(col_name, prefixes, suffixes, words, expected):
    """If the column name already looks like a status or category column, we trust
    the name and give a full score right away. The mocked data is empty on
    purpose: if the name check did not stop early, the score would fall to the
    minimum."""
    cleaner = EnumCleaner(
        cases=["a"],
        cleaner_matching_prefixes=prefixes,
        cleaner_matching_suffixes=suffixes,
        cleaner_matching_words=words,
    )
    # Name-based matching (prefix/suffix/word) must short-circuit before any
    # value-based auto matching is attempted, so an empty collect() is fine.
    mock_df = _mock_df_with_value_counts([])
    assert cleaner.match_score(mock_df, (col_name,)) == expected


# ==============================================================================
# 1b. MATCH SCORE: VALUE-BASED AUTO MATCHING
# ==============================================================================


def test_match_score_auto_matches_by_value_when_name_does_not_match():
    """Here the name tells us nothing, so we look at the values. Eight of ten rows
    are known cases, so the score is 0.8, simply the share of rows that fit."""
    cleaner = EnumCleaner(cases=["active", "inactive"])
    mock_df = _mock_df_with_value_counts(
        [("active", 5), ("inactive", 3), ("unknown", 2)]
    )
    # 5 + 3 matched out of 10 total occurrences
    assert cleaner.match_score(mock_df, ("status",)) == pytest.approx(0.8)


def test_match_score_auto_matching_all_values_match():
    """When every value in the column is one of the known cases, we are as sure as we
    can be. The score is the maximum."""
    cleaner = EnumCleaner(cases=["active", "inactive"])
    mock_df = _mock_df_with_value_counts([("active", 4), ("inactive", 6)])
    assert cleaner.match_score(mock_df, ("status",)) == EnumCleaner.MAX_SCORE


def test_match_score_auto_matching_no_values_match():
    """If none of the values are known cases, this column is clearly not ours. It
    gets the lowest score so another cleaner can claim it."""
    cleaner = EnumCleaner(cases=["active", "inactive"])
    mock_df = _mock_df_with_value_counts([("pending", 1), ("archived", 9)])
    assert cleaner.match_score(mock_df, ("status",)) == EnumCleaner.MIN_SCORE


def test_match_score_auto_matching_with_no_rows_returns_min_score():
    """An empty column gives us nothing to judge by. We return the lowest score
    instead of dividing by zero."""
    cleaner = EnumCleaner(cases=["active", "inactive"])
    mock_df = _mock_df_with_value_counts([])
    assert cleaner.match_score(mock_df, ("status",)) == EnumCleaner.MIN_SCORE


def test_match_score_auto_matching_uses_registered_matchers():
    """Scoring should understand a case the same way cleaning does. So a slightly
    misspelled value still counts through the fuzzy matcher, while a random string
    does not."""
    # Value-based matching goes through the compiled case matchers, so
    # non-exact matcher types (e.g. fuzzy/regex) participate too.
    cleaner = EnumCleaner(
        cases={
            "male": EnumCleaner.FuzzyMatcher(variants={"male"}, threshold=0.8),
        }
    )
    mock_df = _mock_df_with_value_counts([("male", 8), ("mal", 1), ("xyz123", 1)])
    # "male" and "mal" (close fuzzy match) count, "xyz123" does not
    assert cleaner.match_score(mock_df, ("gender",)) == pytest.approx(9 / 10)


def test_match_score_auto_matching_queries_expected_dataframe_chain():
    """To keep scoring cheap on big tables we only look at the 100 most common
    values, after trimming and dropping blanks. This test pins down that exact
    query so nobody accidentally turns it into a full scan."""
    cleaner = EnumCleaner(cases=["active"])
    mock_df = _mock_df_with_value_counts([("active", 1)])
    cleaner.match_score(mock_df, ("status",))

    mock_df.select.assert_called_once_with("status")
    mock_df.select.return_value.strip.assert_called_once_with()
    mock_df.select.return_value.strip.return_value.nullif.assert_called_once_with()
    (
        mock_df.select.return_value.strip.return_value.nullif.return_value.filter_null.assert_called_once_with()
    )
    (
        mock_df.select.return_value.strip.return_value.nullif.return_value.filter_null.return_value.group_by.assert_called_once_with(
            ["status"]
        )
    )
    order_by_call = mock_df.select.return_value.strip.return_value.nullif.return_value.filter_null.return_value.group_by.return_value.agg.return_value.order_by
    order_by_call.assert_called_once_with("status", desc=True)
    order_by_call.return_value.limit.assert_called_once_with(100)


# ==============================================================================
# 2. CASE COMPILATION TESTS
# ==============================================================================


def test_compile_cases_from_plain_iterable():
    """The simplest way to define cases is a plain list. Each value stands for
    itself, and anything outside the list is treated as unknown and comes back as
    null."""
    cleaner = EnumCleaner(cases=["active", "inactive"])
    assert cleaner.clean_row("active") == "active"
    assert cleaner.clean_row("inactive") == "inactive"
    assert cleaner.clean_row("unknown") is None


def test_compile_cases_from_mapping_of_single_string():
    """A case can map a canonical name to one short spelling. So y becomes yes and n
    becomes no, which is how many source systems store flags."""
    cleaner = EnumCleaner(cases={"yes": "y", "no": "n"})
    assert cleaner.clean_row("y") == "yes"
    assert cleaner.clean_row("n") == "no"


def test_compile_cases_from_mapping_of_iterable():
    """Real data spells the same thing many ways. A case can list all of them, and
    every spelling should clean to the one canonical value."""
    cleaner = EnumCleaner(cases={"male": ["m", "man", "boy"]})
    assert cleaner.clean_row("m") == "male"
    assert cleaner.clean_row("man") == "male"
    assert cleaner.clean_row("boy") == "male"


def test_compile_cases_from_mapping_of_custom_matcher():
    """Sometimes a plain list is not enough, so a case can be given a matcher object
    directly. We expect it to be used exactly as supplied."""
    matcher = EnumCleaner.ExactMatcher(variants={"x"})
    cleaner = EnumCleaner(cases={"matched": matcher})
    assert cleaner.clean_row("x") == "matched"


def test_compile_cases_invalid_matcher_type_raises():
    """If someone passes something that is not a valid case definition, we want to
    hear about it when the cleaner is built. Failing halfway through a big dataset
    would be much harder to debug."""
    with pytest.raises(TypeError, match="Invalid matcher type"):
        EnumCleaner(cases={"bad": 123})


# ==============================================================================
# 3. EXACT MATCHER TESTS
# ==============================================================================


def test_exact_matcher_case_sensitive_by_default():
    """Out of the box the exact matcher is strict, so Yes and yes are different
    values. Being strict first is the safer default, and loosening it is a
    deliberate choice."""
    matcher = EnumCleaner.ExactMatcher(variants={"Yes"})
    assert matcher("Yes") is True
    assert matcher("yes") is False


def test_exact_matcher_case_insensitive():
    """When you do want to be relaxed about capital letters, switching case
    sensitivity off lets yes and YES both match Yes."""
    matcher = EnumCleaner.ExactMatcher(variants={"Yes"}, case_sensitive=False)
    assert matcher("yes") is True
    assert matcher("YES") is True


# ==============================================================================
# 4. REGEX MATCHER TESTS
# ==============================================================================


def test_regex_matcher_fullmatch_from_string_pattern():
    """A pattern has to describe the whole value, not just a piece of it. A phone-
    like number with an extra digit on the end must be rejected, otherwise loose
    patterns would swallow unrelated data."""
    matcher = EnumCleaner.RegexMatcher(pattern=r"\d{3}-\d{4}")
    assert matcher("123-4567") is True
    assert matcher("123-45678") is False  # not a full match


def test_regex_matcher_case_insensitive_by_default_string_pattern():
    """People type the same word in all sorts of capitalisation. So a pattern given
    as plain text ignores case unless you say otherwise."""
    matcher = EnumCleaner.RegexMatcher(pattern=r"yes")
    assert matcher("YES") is True


def test_regex_matcher_precompiled_pattern_respects_case_sensitivity():
    """If you hand over a pattern you compiled yourself, the matcher should still
    honour its own case setting. Otherwise the option would only work for half of
    the ways to build one."""
    import re

    matcher = EnumCleaner.RegexMatcher(pattern=re.compile(r"yes"), case_sensitive=False)
    assert matcher("YES") is True
    matcher_cs = EnumCleaner.RegexMatcher(pattern=re.compile(r"yes"))
    assert matcher_cs("YES") is False


# ==============================================================================
# 5. FUZZY MATCHER TESTS
# ==============================================================================


def test_fuzzy_matcher_matches_close_variant():
    """Typos are the whole reason fuzzy matching exists. A value missing its last
    letter is still close enough to active to match."""
    matcher = EnumCleaner.FuzzyMatcher(variants={"active"}, threshold=0.8)
    assert matcher("activ") is True


def test_fuzzy_matcher_rejects_below_threshold():
    """The threshold is how strict the matcher is. With a very high bar, a value that
    is noticeably off is turned away."""
    matcher = EnumCleaner.FuzzyMatcher(variants={"active"}, threshold=0.95)
    assert matcher("actv") is False


def test_fuzzy_matcher_invalid_threshold_raises():
    """Similarity is a number between 0 and 1, so a threshold of 1.5 can only be a
    mistake. We refuse it straight away with a clear error."""
    with pytest.raises(ValueError, match="threshold must be between"):
        EnumCleaner.FuzzyMatcher(variants={"active"}, threshold=1.5)


def test_fuzzy_matcher_case_insensitive():
    """Capital letters should not count as spelling mistakes. With case sensitivity
    off, a shouted ACTIV still matches active."""
    matcher = EnumCleaner.FuzzyMatcher(
        variants={"active"}, threshold=0.8, case_sensitive=False
    )
    assert matcher("ACTIV") is True


# ==============================================================================
# 6. COMBINED MATCHER TESTS
# ==============================================================================


def test_combined_matcher_matches_if_any_submatcher_matches():
    """A combined matcher is an either-or. If any one of its parts accepts the value
    it matches, and a value that none accept is rejected."""
    matcher = EnumCleaner.CombinedMatcher(
        matchers=[
            EnumCleaner.ExactMatcher(variants={"y"}),
            EnumCleaner.ExactMatcher(variants={"yes"}),
        ]
    )
    assert matcher("y") is True
    assert matcher("yes") is True
    assert matcher("no") is False


def test_combined_matcher_via_enum_cleaner_case():
    """Here a combined matcher is used as a case, mixing an exact check for m with a
    pattern for male. Both clean to male, and female is not accepted by either."""
    combined = EnumCleaner.CombinedMatcher(
        matchers=[
            EnumCleaner.ExactMatcher(variants={"m"}),
            EnumCleaner.RegexMatcher(pattern=r"male"),
        ]
    )
    cleaner = EnumCleaner(cases={"male": combined})
    assert cleaner.clean_row("m") == "male"
    assert cleaner.clean_row("male") == "male"
    assert cleaner.clean_row("female") is None


# ==============================================================================
# 7. VALUE INPUT CONTRACT TESTS
# ==============================================================================


def test_clean_row_asserts_non_empty_stripped_input():
    """This cleaner assumes the pipeline already trimmed the value and removed
    blanks. If an empty or padded value ever reaches it, that is a bug elsewhere,
    and we want it to fail loudly."""
    cleaner = EnumCleaner(cases=["a"])
    with pytest.raises(AssertionError):
        cleaner.clean_row("")
    with pytest.raises(AssertionError):
        cleaner.clean_row(" a ")


def test_clean_row_first_matching_case_wins_on_order():
    """If two cases both claim the same value, the one listed first wins. That keeps
    the result predictable and lets you order cases by priority."""
    cleaner = EnumCleaner(
        cases={"first": ["dup"], "second": ["dup"]},
    )
    assert cleaner.clean_row("dup") == "first"


def test_enum_cleaner_numeric_column_needs_every_value_accepted():
    """Numbers match small enums by accident all the time. So a number column is only
    taken if every single value is a known case, and one stray 7 is enough to walk
    away."""
    import pandas as pd
    from dataclean_pandas import PandasDataFrame

    from dataclean import EnumCleaner

    cleaner = EnumCleaner(cases={"on": ["1"], "off": ["0"]})
    only_flags = PandasDataFrame(df=pd.DataFrame({"x": [0, 1, 1, 0]}))
    with_other = PandasDataFrame(df=pd.DataFrame({"x": [0, 1, 1, 7]}))

    assert cleaner.match_score(only_flags, ("x",)) == EnumCleaner.MAX_SCORE
    assert cleaner.match_score(with_other, ("x",)) == EnumCleaner.MIN_SCORE


# ==============================================================================
# 1c. MATCH SCORE: DIGIT-ONLY VALUES
# ==============================================================================


def test_match_score_digit_only_column_needs_every_value_to_match():
    """A column of nothing but digits looks a lot like ids or counts. If some of the
    values are not cases, we score it zero even though a few happen to match."""
    # Values 3 to 5 are not cases, so the ids-like column scores zero even
    # though "1" and "2" match.
    cleaner = EnumCleaner(cases=["1", "2"])
    mock_df = _mock_df_with_value_counts([("1", 4), ("2", 3), ("3", 2), ("5", 1)])
    assert cleaner.match_score(mock_df, ("kind",)) == EnumCleaner.MIN_SCORE


def test_match_score_digit_only_column_scores_full_when_all_match():
    """A digit-only column is fine when every value is a known case, like a small
    code list of 1 and 2. In that situation the score is the maximum."""
    cleaner = EnumCleaner(cases=["1", "2"])
    mock_df = _mock_df_with_value_counts([("1", 4), ("2", 3)])
    assert cleaner.match_score(mock_df, ("kind",)) == EnumCleaner.MAX_SCORE


def test_match_score_digit_values_count_in_a_mixed_column():
    """When the column also holds letters like m and f, the evidence is much
    stronger. So the digit value 1 counts as a match here, giving 9 out of 10."""
    cleaner = EnumCleaner(cases=["m", "f", "1", "2"])
    mock_df = _mock_df_with_value_counts([("m", 4), ("f", 4), ("1", 1), ("x", 1)])
    # "m", "f" and "1" all count, since non-digit values match as well
    assert cleaner.match_score(mock_df, ("kind",)) == pytest.approx(0.9)


def test_match_score_digits_alone_do_not_carry_a_mixed_column():
    """Here most matches are digits and one value is clearly something else. Digits
    alone are not enough evidence to claim a column that is not purely digits, so
    the score is the minimum."""
    cleaner = EnumCleaner(cases=["1", "2"])
    mock_df = _mock_df_with_value_counts([("1", 8), ("2", 1), ("x", 1)])
    assert cleaner.match_score(mock_df, ("kind",)) == EnumCleaner.MIN_SCORE


def test_match_score_digit_values_count_on_a_name_hit():
    """If the column name already says kind, we trust it. Digit values then count as
    normal, and the unknown 9 does not drag the score down."""
    cleaner = EnumCleaner(cases=["1", "2"], cleaner_matching_words=("kind",))
    mock_df = _mock_df_with_value_counts([("1", 4), ("9", 3)])
    assert cleaner.match_score(mock_df, ("kind",)) == EnumCleaner.MAX_SCORE
