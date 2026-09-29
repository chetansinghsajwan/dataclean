from unittest.mock import MagicMock

import pytest

from dataclean.cleaners.enum_cleaner import EnumCleaner
from dataclean.engine.dataframe import DataFrame

# ==============================================================================
# 1. CORE METADATA & MATCH SCORE TESTS
# ==============================================================================


def test_enum_cleaner_metadata():
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
    cleaner = EnumCleaner(cases=["active", "inactive"])
    mock_df = _mock_df_with_value_counts(
        [("active", 5), ("inactive", 3), ("unknown", 2)]
    )
    # 5 + 3 matched out of 10 total occurrences
    assert cleaner.match_score(mock_df, ("status",)) == pytest.approx(0.8)


def test_match_score_auto_matching_all_values_match():
    cleaner = EnumCleaner(cases=["active", "inactive"])
    mock_df = _mock_df_with_value_counts([("active", 4), ("inactive", 6)])
    assert cleaner.match_score(mock_df, ("status",)) == EnumCleaner.MAX_SCORE


def test_match_score_auto_matching_no_values_match():
    cleaner = EnumCleaner(cases=["active", "inactive"])
    mock_df = _mock_df_with_value_counts([("pending", 1), ("archived", 9)])
    assert cleaner.match_score(mock_df, ("status",)) == EnumCleaner.MIN_SCORE


def test_match_score_auto_matching_with_no_rows_returns_min_score():
    cleaner = EnumCleaner(cases=["active", "inactive"])
    mock_df = _mock_df_with_value_counts([])
    assert cleaner.match_score(mock_df, ("status",)) == EnumCleaner.MIN_SCORE


def test_match_score_auto_matching_uses_registered_matchers():
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
    cleaner = EnumCleaner(cases=["active", "inactive"])
    assert cleaner.clean_row("active") == "active"
    assert cleaner.clean_row("inactive") == "inactive"
    assert cleaner.clean_row("unknown") is None


def test_compile_cases_from_mapping_of_single_string():
    cleaner = EnumCleaner(cases={"yes": "y", "no": "n"})
    assert cleaner.clean_row("y") == "yes"
    assert cleaner.clean_row("n") == "no"


def test_compile_cases_from_mapping_of_iterable():
    cleaner = EnumCleaner(cases={"male": ["m", "man", "boy"]})
    assert cleaner.clean_row("m") == "male"
    assert cleaner.clean_row("man") == "male"
    assert cleaner.clean_row("boy") == "male"


def test_compile_cases_from_mapping_of_custom_matcher():
    matcher = EnumCleaner.ExactMatcher(variants={"x"})
    cleaner = EnumCleaner(cases={"matched": matcher})
    assert cleaner.clean_row("x") == "matched"


def test_compile_cases_invalid_matcher_type_raises():
    with pytest.raises(TypeError, match="Invalid matcher type"):
        EnumCleaner(cases={"bad": 123})


# ==============================================================================
# 3. EXACT MATCHER TESTS
# ==============================================================================


def test_exact_matcher_case_sensitive_by_default():
    matcher = EnumCleaner.ExactMatcher(variants={"Yes"})
    assert matcher("Yes") is True
    assert matcher("yes") is False


def test_exact_matcher_case_insensitive():
    matcher = EnumCleaner.ExactMatcher(variants={"Yes"}, case_sensitive=False)
    assert matcher("yes") is True
    assert matcher("YES") is True


# ==============================================================================
# 4. REGEX MATCHER TESTS
# ==============================================================================


def test_regex_matcher_fullmatch_from_string_pattern():
    matcher = EnumCleaner.RegexMatcher(pattern=r"\d{3}-\d{4}")
    assert matcher("123-4567") is True
    assert matcher("123-45678") is False  # not a full match


def test_regex_matcher_case_insensitive_by_default_string_pattern():
    matcher = EnumCleaner.RegexMatcher(pattern=r"yes")
    assert matcher("YES") is True


def test_regex_matcher_precompiled_pattern_respects_case_sensitivity():
    import re

    matcher = EnumCleaner.RegexMatcher(pattern=re.compile(r"yes"), case_sensitive=False)
    assert matcher("YES") is True
    matcher_cs = EnumCleaner.RegexMatcher(pattern=re.compile(r"yes"))
    assert matcher_cs("YES") is False


# ==============================================================================
# 5. FUZZY MATCHER TESTS
# ==============================================================================


def test_fuzzy_matcher_matches_close_variant():
    matcher = EnumCleaner.FuzzyMatcher(variants={"active"}, threshold=0.8)
    assert matcher("activ") is True


def test_fuzzy_matcher_rejects_below_threshold():
    matcher = EnumCleaner.FuzzyMatcher(variants={"active"}, threshold=0.95)
    assert matcher("actv") is False


def test_fuzzy_matcher_invalid_threshold_raises():
    with pytest.raises(ValueError, match="threshold must be between"):
        EnumCleaner.FuzzyMatcher(variants={"active"}, threshold=1.5)


def test_fuzzy_matcher_case_insensitive():
    matcher = EnumCleaner.FuzzyMatcher(
        variants={"active"}, threshold=0.8, case_sensitive=False
    )
    assert matcher("ACTIV") is True


# ==============================================================================
# 6. COMBINED MATCHER TESTS
# ==============================================================================


def test_combined_matcher_matches_if_any_submatcher_matches():
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
    cleaner = EnumCleaner(cases=["a"])
    with pytest.raises(AssertionError):
        cleaner.clean_row("")
    with pytest.raises(AssertionError):
        cleaner.clean_row(" a ")


def test_clean_row_first_matching_case_wins_on_order():
    cleaner = EnumCleaner(
        cases={"first": ["dup"], "second": ["dup"]},
    )
    assert cleaner.clean_row("dup") == "first"
