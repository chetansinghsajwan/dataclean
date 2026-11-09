from unittest.mock import MagicMock

import pytest

from dataclean import Cleaner, CountryCleaner, DataFrame, DataType

# ==============================================================================
# 1. CORE PROPERTY TESTS
# ==============================================================================


def test_cleaner_metadata():

    cleaner = CountryCleaner()
    assert cleaner.name == "CountryCleaner"
    assert len(cleaner.inputs.cols) == 1
    assert len(cleaner.outputs.cols) == 1
    assert cleaner.outputs.cols[0].dtype == DataType.STR


@pytest.mark.parametrize(
    "col_name, expected_confidence",
    [
        ("country_name", Cleaner.MAX_SCORE),
        ("COUNTRY", Cleaner.MAX_SCORE),
        ("user_country_code", Cleaner.MAX_SCORE),
        ("email_address", Cleaner.MIN_SCORE),
        ("id", Cleaner.MIN_SCORE),
    ],
)
def test_match_score(col_name, expected_confidence):
    cleaner = CountryCleaner()
    mock_df = MagicMock(spec=DataFrame)
    assert cleaner.match_score(mock_df, (col_name,)) == expected_confidence


# ==============================================================================
# 2. FORMAT INITIALIZATION & PIPELINE RESOLUTION TESTS
# ==============================================================================


def test_default_initialization_pipeline():

    cleaner = CountryCleaner()
    assert cleaner.resolved_in_formats == (
        CountryCleaner.Format.ALPHA2,
        CountryCleaner.Format.ALPHA3,
        CountryCleaner.Format.NAME,
        CountryCleaner.Format.NAME_FUZZY,
    )

    cleaner = CountryCleaner(in_format=CountryCleaner.Format.AUTO)
    assert cleaner.resolved_in_formats == (
        CountryCleaner.Format.ALPHA2,
        CountryCleaner.Format.ALPHA3,
        CountryCleaner.Format.NAME,
        CountryCleaner.Format.NAME_FUZZY,
    )


def test_custom_single_format_pipeline():
    cleaner = CountryCleaner(in_format=CountryCleaner.Format.ALPHA2)
    assert cleaner.resolved_in_formats == (CountryCleaner.Format.ALPHA2,)


def test_custom_tuple_format_pipeline_deduplication():
    cleaner = CountryCleaner(
        in_format=(CountryCleaner.Format.ALPHA2, CountryCleaner.Format.AUTO)
    )

    assert cleaner.resolved_in_formats == (
        CountryCleaner.Format.ALPHA2,
        CountryCleaner.Format.ALPHA3,
        CountryCleaner.Format.NAME,
        CountryCleaner.Format.NAME_FUZZY,
    )

    cleaner = CountryCleaner(
        in_format=(CountryCleaner.Format.ALPHA3, CountryCleaner.Format.AUTO)
    )
    assert cleaner.resolved_in_formats == (
        CountryCleaner.Format.ALPHA3,
        CountryCleaner.Format.ALPHA2,
        CountryCleaner.Format.NAME,
        CountryCleaner.Format.NAME_FUZZY,
    )


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
        (
            "Lets go to india",
            CountryCleaner.Format.NAME_FUZZY,
            CountryCleaner.Format.NAME,
            "India",
        ),
        (
            "hi indIA",
            CountryCleaner.Format.NAME_FUZZY,
            CountryCleaner.Format.NAME,
            "India",
        ),
    ],
)
def test_clean_row_success(input_value, in_fmt, out_fmt, expected_output):
    cleaner = CountryCleaner(in_format=in_fmt, out_format=out_fmt)
    assert cleaner.clean_row(input_value) == expected_output


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
def test_clean_row_returns_none_on_miss(input_value, in_fmt):
    cleaner = CountryCleaner(in_format=in_fmt)
    assert cleaner.clean_row(input_value) is None


# ==============================================================================
# 4. EXACT NAMES, ALIASES AND AMBIGUITY
# ==============================================================================


@pytest.mark.parametrize(
    "input_value, expected_output",
    [
        ("U.S.A.", "United States"),
        ("USA", "United States"),
        ("America", "United States"),
        ("U.A.E.", "United Arab Emirates"),
        ("Deutschland", "Germany"),
        ("Turkey", "Türkiye"),
        ("Ivory Coast", "Côte d'Ivoire"),
        ("Cote d'Ivoire", "Côte d'Ivoire"),
        ("Burma", "Myanmar"),
        ("Bharat", "India"),
        ("Holland", "Netherlands"),
        ("The Netherlands", "Netherlands"),
        ("England", "United Kingdom"),
        ("Czech Republic", "Czechia"),
    ],
)
def test_names_and_aliases(input_value, expected_output):
    assert CountryCleaner().clean_row(input_value) == expected_output


@pytest.mark.parametrize(
    "input_value, expected_output",
    [("Niger", "Niger"), ("Oman", "Oman"), ("Guinea", "Guinea"), ("India", "India")],
)
def test_exact_names_do_not_match_a_longer_name(input_value, expected_output):
    assert CountryCleaner().clean_row(input_value) == expected_output


@pytest.mark.parametrize("input_value", ["Man", "Kosovo", "Atlantis", "unknown"])
def test_wrong_substring_matches_become_none(input_value):
    assert CountryCleaner().clean_row(input_value) is None


@pytest.mark.parametrize("input_value", ["Korea", "Congo", "korea"])
def test_ambiguous_names_become_none(input_value):
    assert CountryCleaner().clean_row(input_value) is None


def test_short_values_are_never_fuzzy_matched():
    cleaner = CountryCleaner(in_format=CountryCleaner.Format.NAME_FUZZY)
    assert cleaner.clean_row("Indi") is None
    assert cleaner.clean_row("Indian") == "India"


# ==============================================================================
# 5. COMMON NAMES
# ==============================================================================


@pytest.mark.parametrize(
    "input_value, expected_output",
    [
        ("KR", "South Korea"),
        ("Korea, Republic of", "South Korea"),
        ("IR", "Iran"),
        ("TW", "Taiwan"),
        ("VN", "Vietnam"),
        ("RU", "Russia"),
        ("PS", "Palestine"),
        ("CD", "DR Congo"),
    ],
)
def test_output_uses_common_names_by_default(input_value, expected_output):
    assert CountryCleaner().clean_row(input_value) == expected_output


def test_common_names_can_be_turned_off():
    cleaner = CountryCleaner(common_names=False)
    assert cleaner.clean_row("KR") == "Korea, Republic of"
    assert cleaner.clean_row("RU") == "Russian Federation"
    assert cleaner.clean_row("IN") == "India"


def test_alpha_output_is_unaffected_by_common_names():
    cleaner = CountryCleaner(out_format=CountryCleaner.Format.ALPHA3)
    assert cleaner.clean_row("South Korea") == "KOR"


@pytest.mark.parametrize(
    "input_value, expected",
    [
        ("Indai", "India"),
        ("Gremany", "Germany"),
        ("Frnace", "France"),
        ("Austrlia", "Australia"),
    ],
)
def test_a_name_one_edit_away_is_matched(input_value, expected):
    assert CountryCleaner().clean_row(input_value) == expected


def test_a_name_one_edit_from_two_countries_is_not_matched():
    # "Jambia" is one edit from both Gambia and Zambia.
    assert CountryCleaner().clean_row("Jambia") is None
