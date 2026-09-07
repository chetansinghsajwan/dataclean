import pytest

from dataclean import DataType, GenderCleaner

# ==============================================================================
# 1. CORE PROPERTY TESTS
# ==============================================================================


def test_gender_cleaner_metadata():
    cleaner = GenderCleaner()
    assert cleaner.name == "GenderCleaner"
    assert len(cleaner.outputs.cols) == 1
    assert cleaner.outputs.cols[0].dtype == DataType.STR


@pytest.mark.parametrize(
    "col_name, expected_confidence",
    [
        ("gender", 1.0),
        ("SEX", 1.0),
        ("user_gender_id", 1.0),
        ("first_name", 0.0),
        ("country", 0.0),
    ],
)
def test_gender_cleaner_confidence_heuristics(
    col_name, expected_confidence, mock_df_with_value_counts
):
    cleaner = GenderCleaner()
    # Name-based matching (matching word) short-circuits before value-based
    # auto matching, so an empty collect() is fine for all cases here.
    mock_df = mock_df_with_value_counts([])
    assert cleaner.match_score(mock_df, (col_name,)) == expected_confidence


# ==============================================================================
# 1b. MATCH SCORE: VALUE-BASED AUTO MATCHING (inherited from EnumCleaner)
# ==============================================================================


def test_gender_cleaner_auto_matches_by_value_when_name_does_not_match(
    mock_df_with_value_counts,
):
    # "identity" hits neither the "gender"/"sex" match words nor any prefix/suffix
    cleaner = GenderCleaner()
    mock_df = mock_df_with_value_counts([("male", 6), ("female", 4)])
    assert cleaner.match_score(mock_df, ("identity",)) == GenderCleaner.MAX_SCORE


def test_gender_cleaner_auto_matching_partial_ratio(mock_df_with_value_counts):
    cleaner = GenderCleaner()
    mock_df = mock_df_with_value_counts(
        [("male", 3), ("female", 3), ("unknown", 4)],
    )
    # 3 + 3 matched out of 10 total occurrences
    assert cleaner.match_score(mock_df, ("identity",)) == pytest.approx(0.6)


def test_gender_cleaner_auto_matching_no_values_match(mock_df_with_value_counts):
    cleaner = GenderCleaner()
    mock_df = mock_df_with_value_counts([("north", 1), ("south", 1)])
    assert cleaner.match_score(mock_df, ("identity",)) == GenderCleaner.MIN_SCORE


def test_gender_cleaner_auto_matching_case_insensitive(mock_df_with_value_counts):
    cleaner = GenderCleaner()
    mock_df = mock_df_with_value_counts([("MALE", 1), ("Female", 1)])
    assert cleaner.match_score(mock_df, ("identity",)) == GenderCleaner.MAX_SCORE


# ==============================================================================
# 2. STRUCTURAL STR-ENUM TRANSFORMATION MAPPING TESTS
# ==============================================================================


@pytest.mark.parametrize(
    "input_value, target_format, expected_output",
    [
        # --- Male Mapping Permutations ---
        ("male", GenderCleaner.Format.FULL, "Male"),
        ("m", GenderCleaner.Format.FULL, "Male"),
        ("man", GenderCleaner.Format.FULL, "Male"),
        ("boy", GenderCleaner.Format.FULL, "Male"),
        ("male", GenderCleaner.Format.CHAR, "M"),
        ("male", GenderCleaner.Format.BINARY, "1"),
        # --- Female Mapping Permutations ---
        ("female", GenderCleaner.Format.FULL, "Female"),
        ("f", GenderCleaner.Format.FULL, "Female"),
        ("woman", GenderCleaner.Format.FULL, "Female"),
        ("girl", GenderCleaner.Format.FULL, "Female"),
        ("female", GenderCleaner.Format.CHAR, "F"),
        ("female", GenderCleaner.Format.BINARY, "0"),
        # --- Other/Non-Binary Mapping Permutations ---
        ("other", GenderCleaner.Format.FULL, "Other"),
        ("o", GenderCleaner.Format.FULL, "Other"),
        ("non-binary", GenderCleaner.Format.FULL, "Other"),
        ("other", GenderCleaner.Format.CHAR, "O"),
        ("other", GenderCleaner.Format.BINARY, "-1"),
    ],
)
def test_clean_value_format_translations(input_value, target_format, expected_output):
    cleaner = GenderCleaner(format=target_format)
    assert cleaner.clean_row(input_value) == expected_output


# ==============================================================================
# 3. CASE INSENSITIVITY & MISS PROCESSING TESTS
# ==============================================================================


@pytest.mark.parametrize(
    "cased_input",
    ["MALE", "Male", "mAlE", "F", "Female", "OTHER", "Non-Binary"],
)
def test_clean_value_handles_mixed_casing(cased_input):
    cleaner = GenderCleaner(format=GenderCleaner.Format.FULL)
    # Even with random data entry casing variations, mapping lookup should be successful
    assert cleaner.clean_row(cased_input) in ["Male", "Female", "Other"]


def test_clean_value_returns_none_on_unmapped_token():
    cleaner = GenderCleaner()
    # If the token exists but isn't part of our domain map, return None safely
    assert cleaner.clean_row("unknown_variant") is None
    assert cleaner.clean_row("alien") is None
