from unittest.mock import MagicMock

import pytest

from dataclean import DataFrame
from dataclean.cleaners.enum_cleaner import EnumCleaner

# ==============================================================================
# 1. CORE METADATA & MATCH SCORE TESTS
# ==============================================================================


def test_enum_cleaner_metadata():
    cleaner = EnumCleaner(cases=["a", "b"])
    assert cleaner.name == "EnumCleaner"


@pytest.mark.parametrize(
    "col_name, prefixes, suffixes, words, expected",
    [
        ("status_code", ("status",), (), (), EnumCleaner.MAX_SCORE),
        ("order_status", (), ("status",), (), EnumCleaner.MAX_SCORE),
        ("user_category", (), (), ("category",), EnumCleaner.MAX_SCORE),
        ("first_name", ("status",), ("status",), ("category",), EnumCleaner.MIN_SCORE),
    ],
)
def test_match_score(col_name, prefixes, suffixes, words, expected):
    cleaner = EnumCleaner(
        cases=["a"],
        cleaner_matching_prefixes=prefixes,
        cleaner_matching_suffixes=suffixes,
        cleaner_matching_words=words,
    )
    mock_df = MagicMock(spec=DataFrame)
    assert (
        cleaner.match_score(mock_df, ("col_name" if False else col_name,)) == expected
    )


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
