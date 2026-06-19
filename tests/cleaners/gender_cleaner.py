from unittest.mock import MagicMock

import pytest

from dataclean.cleaners.gender_cleaner import GenderCleaner

# ==============================================================================
# 1. CORE PROPERTY TESTS
# ==============================================================================


def test_gender_cleaner_metadata():
    cleaner = GenderCleaner()
    assert cleaner.name() == "GenderCleaner"
    assert cleaner.output_schema() == "str"


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
def test_gender_cleaner_confidence_heuristics(col_name, expected_confidence):
    cleaner = GenderCleaner()
    mock_df = MagicMock()
    assert cleaner.get_data_type_confidence(mock_df, (col_name,)) == expected_confidence


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
    cleaner = GenderCleaner(out_format=target_format)
    assert cleaner.clean_value(input_value) == expected_output


# ==============================================================================
# 3. CASE INSENSITIVITY & MISS PROCESSING TESTS
# ==============================================================================


@pytest.mark.parametrize(
    "cased_input",
    ["MALE", "Male", "mAlE", "F", "Female", "OTHER", "Non-Binary"],
)
def test_clean_value_handles_mixed_casing(cased_input):
    cleaner = GenderCleaner(out_format=GenderCleaner.Format.FULL)
    # Even with random data entry casing variations, mapping lookup should be successful
    assert cleaner.clean_value(cased_input) in ["Male", "Female", "Other"]


def test_clean_value_returns_none_on_unmapped_token():
    cleaner = GenderCleaner()
    # If the token exists but isn't part of our domain map, return None safely
    assert cleaner.clean_value("unknown_variant") is None
    assert cleaner.clean_value("alien") is None
