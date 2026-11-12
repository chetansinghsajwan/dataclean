"""Gender cleaner tests: name and value detection, mapping to output formats, typo handling and config."""

import pytest

from dataclean import DataType, GenderCleaner

# ==============================================================================
# 1. CORE PROPERTY TESTS
# ==============================================================================


def test_gender_cleaner_metadata():
    """A quick sanity check on the cleaner's identity. It should call itself GenderCleaner and hand back one text column, which is what the pipeline relies on when wiring cleaners together."""
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
    """Here only the column name varies. Names like gender, sex or user_gender_id should get full marks and unrelated ones like country should get none, and we pass an empty value sample to show the name alone settles it."""
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
    """The column is called identity, which tells us nothing, but every value is male or female. We still want the cleaner to claim it, because real files often have badly named columns."""
    # "identity" hits neither the "gender"/"sex" match words nor any prefix/suffix
    cleaner = GenderCleaner()
    mock_df = mock_df_with_value_counts([("male", 6), ("female", 4)])
    assert cleaner.match_score(mock_df, ("identity",)) == GenderCleaner.MAX_SCORE


def test_gender_cleaner_auto_matching_partial_ratio(mock_df_with_value_counts):
    """Eight of ten values are genders and two are unknown. The score should be 0.8, the share of values that fit, so a mostly-gender column ranks high without claiming to be perfect."""
    cleaner = GenderCleaner()
    mock_df = mock_df_with_value_counts(
        [("male", 4), ("female", 4), ("unknown", 2)],
    )
    # 4 + 4 matched out of 10 total occurrences
    assert cleaner.match_score(mock_df, ("identity",)) == pytest.approx(0.8)


def test_gender_cleaner_auto_matching_below_threshold_scores_zero(
    mock_df_with_value_counts,
):
    """Only sixty percent of the values are genders, which is under the seventy percent bar for name-less detection. At that point it is more likely some other column, so the cleaner steps back and scores zero."""
    cleaner = GenderCleaner()
    mock_df = mock_df_with_value_counts(
        [("male", 3), ("female", 3), ("unknown", 4)],
    )
    # 60% matched, under the 70% value-only threshold
    assert cleaner.match_score(mock_df, ("identity",)) == GenderCleaner.MIN_SCORE


def test_gender_cleaner_auto_matching_no_values_match(mock_df_with_value_counts):
    """A column of compass directions has nothing gender-like in it. It should score zero so we never grab it by accident."""
    cleaner = GenderCleaner()
    mock_df = mock_df_with_value_counts([("north", 1), ("south", 1)])
    assert cleaner.match_score(mock_df, ("identity",)) == GenderCleaner.MIN_SCORE


def test_gender_cleaner_auto_matching_case_insensitive(mock_df_with_value_counts):
    """Values arrive as MALE and Female in whatever case the source used. Detection should treat them the same as lowercase, because capitalisation says nothing about meaning."""
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
        ("male", GenderCleaner.Format.BINARY, 1),
        # --- Female Mapping Permutations ---
        ("female", GenderCleaner.Format.FULL, "Female"),
        ("f", GenderCleaner.Format.FULL, "Female"),
        ("woman", GenderCleaner.Format.FULL, "Female"),
        ("girl", GenderCleaner.Format.FULL, "Female"),
        ("female", GenderCleaner.Format.CHAR, "F"),
        ("female", GenderCleaner.Format.BINARY, 0),
        # --- Other/Non-Binary Mapping Permutations ---
        ("other", GenderCleaner.Format.FULL, "Other"),
        ("o", GenderCleaner.Format.FULL, "Other"),
        ("non-binary", GenderCleaner.Format.FULL, "Other"),
        ("other", GenderCleaner.Format.CHAR, "O"),
        ("other", GenderCleaner.Format.BINARY, -1),
    ],
)
def test_clean_value_format_translations(input_value, target_format, expected_output):
    """Each known way of writing a gender, from M to Non-Binary, is fed in and the answer is checked in each output style. Whatever the source used, everyone ends up with the same spelling."""
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
    """Data entry is messy, so we try shouting, odd mixed case and abbreviations. All of them should still land on Male, Female or Other, since the casing was never part of the meaning."""
    cleaner = GenderCleaner(format=GenderCleaner.Format.FULL)
    # Even with random data entry casing variations, mapping lookup should be successful
    assert cleaner.clean_row(cased_input) in ["Male", "Female", "Other"]


def test_clean_value_returns_none_on_unmapped_token():
    """If a word is not in our gender map, we return null rather than invent an answer. A missing value is easier to deal with than a wrong one."""
    cleaner = GenderCleaner()
    # If the token exists but isn't part of our domain map, return None safely
    assert cleaner.clean_row("unknown_variant") is None
    assert cleaner.clean_row("alien") is None


def _pandas_df(**cols):
    import pandas as pd
    from dataclean_pandas import PandasDataFrame

    return PandasDataFrame(df=pd.DataFrame(cols))


def test_gender_cleaner_rejects_numeric_id_columns():
    """Picture a companyid column that is mostly 1s with a few 2s and 3s. A 1 can look like a gender code, but the spread of other numbers shows it is an ID, so the cleaner must leave it alone."""
    from dataclean import GenderCleaner

    # Mostly 1 (which could look like a gender code) but with other values: an ID.
    df = _pandas_df(companyid=[1, 1, 1, 1, 1, 1, 1, 1, 2, 3])
    assert GenderCleaner().match_score(df, ("companyid",)) == GenderCleaner.MIN_SCORE


def test_gender_cleaner_still_matches_string_values():
    """A guard against over-correcting the ID rule above. A text column of M, F, male and female is clearly gender and should still be picked up."""
    from dataclean import GenderCleaner

    df = _pandas_df(who=["M", "F", "male", "female"])
    assert GenderCleaner().match_score(df, ("who",)) > 0.5


# ==============================================================================
# 4. VARIANTS, TYPOS, ISO 5218 CODES AND UNKNOWN VALUES
# ==============================================================================


@pytest.mark.parametrize(
    "value, expected",
    [
        ("x", "Other"),
        ("X", "Other"),
        ("nonbinary", "Other"),
        ("Non Binary", "Other"),
        ("Transgender", "Other"),
        ("trans", "Other"),
        ("TG", "Other"),
        ("Intersex", "Other"),
        ("Genderqueer", "Other"),
        ("Mr", "Male"),
        ("Sir", "Male"),
        ("he", "Male"),
        ("Gents", "Male"),
        ("Mrs", "Female"),
        ("Ms", "Female"),
        ("Miss", "Female"),
        ("Madam", "Female"),
        ("she", "Female"),
        ("Ladies", "Female"),
    ],
)
def test_gender_cleaner_reads_more_variants(value, expected):
    """Beyond the obvious spellings, people write synonyms and shorthand for the same thing. Each one listed here should land on the right gender."""
    assert GenderCleaner().clean_row(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Mal", "Male"),
        ("Femal", "Female"),
        ("Femlae", "Female"),
        ("Non-binry", "Other"),
        ("Tansgender", "Other"),
    ],
)
def test_gender_cleaner_accepts_small_typos(value, expected):
    """A slip like Femal is easy to make and obvious to a human. The cleaner forgives small typos and maps them to the gender the person meant."""
    assert GenderCleaner().clean_row(value) == expected


def test_gender_cleaner_typos_never_cross_between_genders():
    """Male and female are only a letter or two from words like mail, so a loose typo rule could flip someone's gender. We check that valid words map correctly and near-misses give null, because a wrong answer is worse than none."""
    cleaner = GenderCleaner()
    assert cleaner.clean_row("male") == "Male"
    assert cleaner.clean_row("female") == "Female"
    assert cleaner.clean_row("mail") is None
    assert cleaner.clean_row("mother") is None


def test_gender_cleaner_fuzzy_matching_can_be_turned_off():
    """Some users want only exact spellings. Setting the fuzzy threshold to 1.0 should make Femal null while female still works."""
    cleaner = GenderCleaner(fuzzy_threshold=1.0)
    assert cleaner.clean_row("Femal") is None
    assert cleaner.clean_row("female") == "Female"


@pytest.mark.parametrize(
    "value, expected",
    [("1", "Male"), ("2", "Female"), ("0", None), ("9", None)],
)
def test_gender_cleaner_uses_iso_5218_codes(value, expected):
    """Many systems store gender as the ISO 5218 digits, where 1 is male and 2 is female. Zero and nine mean not known or not applicable, so they become null."""
    assert GenderCleaner().clean_row(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "U",
        "u",
        "Unknown",
        "Not Specified",
        "N/A",
        "alien",
        "Prefer not to say",
        "Prefer not to disclose",
    ],
)
def test_gender_cleaner_unknown_values_become_none(value):
    """People often type that they do not know or would rather not say. Those answers hold no gender, so each of them turns into null."""
    assert GenderCleaner().clean_row(value) is None


# ==============================================================================
# 5. CONFIGURATION
# ==============================================================================


def test_gender_cleaner_binary_output_is_an_integer_column():
    """In binary mode the result is a real whole number and the column is declared as an integer. The char format, by contrast, stays a text column."""
    cleaner = GenderCleaner(format=GenderCleaner.Format.BINARY)
    assert cleaner.outputs.cols[0].dtype == DataType.INT
    assert cleaner.clean_row("m") == 1
    assert isinstance(cleaner.clean_row("f"), int)
    assert GenderCleaner(format=GenderCleaner.Format.CHAR).outputs.cols[0].dtype == (
        DataType.STR
    )


def test_gender_cleaner_honours_custom_matching_words():
    """A team can swap in its own column-name words, such as pronoun. Their word should then match, and the default word gender should stop matching."""
    cleaner = GenderCleaner(cleaner_matching_words=["pronoun"])
    assert cleaner._matches_name("user_pronoun")
    assert not cleaner._matches_name("gender")


def test_gender_cleaner_instances_do_not_share_defaults():
    """We add an extra gender to one cleaner and then build a second one. The second should know nothing about it, which catches the classic bug of default settings shared between instances."""
    first = GenderCleaner(extra_genders={"other": ["mx"]})
    second = GenderCleaner()
    assert first.clean_row("mx") == "Other"
    assert second.clean_row("mx") is None


def test_gender_cleaner_does_not_claim_an_id_like_digit_column(
    mock_df_with_value_counts,
):
    """A contacttypeid column holds 1 to 5, and only 1 and 2 are gender codes. Because other digits turn up in volume, it is an ID and should score zero."""
    # "contacttypeid" holds 1 to 5; only 1 and 2 are gender codes.
    mock_df = mock_df_with_value_counts([("1", 5), ("2", 4), ("3", 3), ("5", 2)])
    cleaner = GenderCleaner()
    assert cleaner.match_score(mock_df, ("contacttypeid",)) == GenderCleaner.MIN_SCORE
