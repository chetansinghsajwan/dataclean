from unittest.mock import MagicMock

import pytest

from dataclean.cleaners.country_cleaner import CountryCleaner

# ==============================================================================
# 1. CORE PROPERTY TESTS
# ==============================================================================


def test_cleaner_metadata():
    cleaner = CountryCleaner()
    assert cleaner.name() == "CountryCleaner"
    assert cleaner.output_schema() == "str"


@pytest.mark.parametrize(
    "col_name, expected_confidence",
    [
        ("country_name", 1.0),
        ("COUNTRY", 1.0),
        ("user_country_code", 1.0),
        ("email_address", 0.0),
        ("id", 0.0),
    ],
)
def test_get_data_type_confidence(col_name, expected_confidence):
    cleaner = CountryCleaner()
    mock_df = MagicMock()
    assert cleaner.get_data_type_confidence(mock_df, (col_name,)) == expected_confidence


# ==============================================================================
# 2. FORMAT INITIALIZATION & PIPELINE RESOLUTION TESTS
# ==============================================================================


def test_default_initialization_pipeline():
    # Defaults to AUTO
    cleaner = CountryCleaner()
    # Auto expands to 3 pipelines (alpha2, alpha3, name)
    assert len(cleaner._find_country_pipeline) == 3


def test_custom_single_format_pipeline():
    cleaner = CountryCleaner(
        in_format=CountryCleaner.Format.ALPHA2, out_format=CountryCleaner.Format.ALPHA3
    )
    assert len(cleaner._find_country_pipeline) == 1


def test_custom_tuple_format_pipeline_deduplication():
    cleaner = CountryCleaner(
        in_format=(CountryCleaner.Format.ALPHA2, CountryCleaner.Format.AUTO)
    )
    # Deduplicates alpha2 out of auto's expansion pool
    assert len(cleaner._find_country_pipeline) == 3


# ==============================================================================
# 3. VALUE CLEANING FUNCTIONAL TESTS
# ==============================================================================


@pytest.mark.parametrize(
    "input_value, in_fmt, out_fmt, expected_output",
    [
        # Standard default matching (Auto -> Name)
        ("IN", CountryCleaner.Format.AUTO, CountryCleaner.Format.NAME, "India"),
        ("IND", CountryCleaner.Format.AUTO, CountryCleaner.Format.NAME, "India"),
        ("india", CountryCleaner.Format.AUTO, CountryCleaner.Format.NAME, "India"),
        # Exact Format Restrictions
        ("IN", CountryCleaner.Format.ALPHA2, CountryCleaner.Format.ALPHA3, "IND"),
        ("IND", CountryCleaner.Format.ALPHA3, CountryCleaner.Format.ALPHA2, "IN"),
        # Fuzzy / Casing Matches
        (
            "United States",
            CountryCleaner.Format.NAME,
            CountryCleaner.Format.ALPHA3,
            "USA",
        ),
        ("in", CountryCleaner.Format.ALPHA2, CountryCleaner.Format.NAME, "India"),
    ],
)
def test_clean_value_success(input_value, in_fmt, out_fmt, expected_output):
    cleaner = CountryCleaner(in_format=in_fmt, out_format=out_fmt)
    assert cleaner.clean_value(input_value) == expected_output


@pytest.mark.parametrize(
    "input_value, in_fmt",
    [
        # Completely invalid values
        ("NotACountry", CountryCleaner.Format.AUTO),
        ("XYZ", CountryCleaner.Format.AUTO),
        # Valid input but bypassed by restricted pipeline settings
        (
            "India",
            CountryCleaner.Format.ALPHA2,
        ),  # "India" is a NAME, but only ALPHA2 allowed
        # ("IN", CountryCleaner.Format.NAME),  # "IN" is an ALPHA2, but only NAME allowed
    ],
)
def test_clean_value_returns_none_on_miss(input_value, in_fmt):
    cleaner = CountryCleaner(in_format=in_fmt)
    assert cleaner.clean_value(input_value) is None
