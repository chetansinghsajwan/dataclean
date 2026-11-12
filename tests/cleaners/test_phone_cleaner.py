"""Tests for PhoneCleaner: metadata, region handling, noise stripping and multi-number cells."""

from unittest.mock import MagicMock

import pytest

from dataclean import DataFrame, PhoneCleaner

# ==============================================================================
# 1. CORE PROPERTIES & HEURISTICS
# ==============================================================================


def test_phone_cleaner_metadata():
    """A fresh phone cleaner should hand back one text column and start with no default
    region. We never want it quietly assuming a country the user did not choose."""
    from dataclean.engine.dataframe import DataType

    cleaner = PhoneCleaner()
    assert cleaner.name == "PhoneCleaner"
    assert len(cleaner.outputs.cols) == 1
    assert cleaner.outputs.cols[0].dtype == DataType.STR
    # Verify the new default configuration is an empty tuple
    assert cleaner.default_regions == ()


@pytest.mark.parametrize(
    "col_name, expected_confidence",
    [
        ("contact_no", 1.0),
        ("mobile_number", 1.0),
        ("user_tel", 1.0),
        ("office_fax", 1.0),
        ("email_address", 0.0),
    ],
)
def test_phone_cleaner_confidence(col_name, expected_confidence):
    """The cleaner looks at column names to decide if it should step in. Names like
    contact_no, mobile_number, tel and fax say yes, while an email column says no,
    so we don't mangle things that aren't phones."""
    cleaner = PhoneCleaner()
    mock_df = MagicMock(spec=DataFrame)
    assert cleaner.match_score(mock_df, (col_name,)) == expected_confidence


# ==============================================================================
# 2. RESILIENT EXTRACTION & FORMATTING LOOPS
# ==============================================================================


@pytest.mark.parametrize(
    "input_val, out_fmt, default_regions, expected_output",
    [
        # --- E.164 Inputs (Self-Detecting, works perfectly with empty default_regions) ---
        ("+91 98765 43210", PhoneCleaner.Format.E164, (), "+919876543210"),
        ("+1-415-555-2671", PhoneCleaner.Format.E164, (), "+14155552671"),
        ("+44 20 7123 1234", PhoneCleaner.Format.E164, (), "+442071231234"),
        # --- Scientific Notation Recovery (Requires fallback since '+' is dropped) ---
        ("9.876543210E+09", PhoneCleaner.Format.E164, ("IN",), "+919876543210"),
        # --- Delimiter & Noise Purging (Requires fallback tuple) ---
        ("011-23456789", PhoneCleaner.Format.E164, ("IN",), "+911123456789"),
        (
            "(415) 555-2671",
            PhoneCleaner.Format.E164,
            ("US", "IN"),
            "+14155552671",
        ),  # Matches US first in the tuple
        # --- Regional & International Fallbacks ---
        ("9876543210", PhoneCleaner.Format.INTERNATIONAL, ("IN",), "+91 98765 43210"),
        ("9876543210", PhoneCleaner.Format.NATIONAL, ("IN",), "098765 43210"),
        ("9876543210", PhoneCleaner.Format.RAW_DIGITS, ("IN",), "919876543210"),
    ],
)
def test_phone_clean_value_success_matrix(
    input_val, out_fmt, default_regions, expected_output
):
    """Here we throw a mix of real-world numbers at it and check the formatted result.
    Numbers starting with a plus carry their own country, but local ones like
    9876543210 can only be read if we tell it a fallback region."""
    cleaner = PhoneCleaner(out_format=out_fmt, default_regions=default_regions)
    assert cleaner.clean_row(input_val) == expected_output


def test_phone_clean_empty_default_region_keeps_unjudgeable_local_numbers():
    """Without a region, a local number like 9876543210 can't be checked, so we just
    tidy the spaces and keep it. Throwing it away would lose data we have no right
    to call bad, whereas a plus-prefixed number is still fully cleaned."""
    # With no region known, a national-format number can't be validated, so it
    # is kept (stripped) rather than silently discarded.
    cleaner = PhoneCleaner()
    assert cleaner.clean_row("9876543210") == "9876543210"
    assert cleaner.clean_row("  011-23456789 ") == "011-23456789"

    # A number with an explicit '+' is self-contained and still gets cleaned.
    assert cleaner.clean_row("+91 98765 43210") == "+919876543210"


def test_phone_clean_known_region_still_drops_invalid_numbers():
    """Once we know the region, we can actually tell what's valid. So a number like
    12345 in India is clearly not real and comes back as null."""
    assert PhoneCleaner(default_regions=("IN",)).clean_row("12345") is None


def test_phone_country_context_selects_region():
    """A row can carry its own country, either a full name or a code. That matters
    because the same digits mean different numbers in different places, so the UK
    row is read as a UK number even with no default region."""
    cleaner = PhoneCleaner()
    assert cleaner.clean_row("020 7357 8775", "United Kingdom") == "+442073578775"
    assert cleaner.clean_row("020 7357 8775", "GB") == "+442073578775"
    assert cleaner.clean_row("9876543210", "India") == "+919876543210"


def test_phone_country_context_is_tried_before_default_regions():
    """When a row says it is from the United Kingdom, that is better information than a
    blanket default of India. So the row's own country gets tried first."""
    cleaner = PhoneCleaner(default_regions=("IN",))
    assert cleaner.clean_row("020 7357 8775", "United Kingdom") == "+442073578775"


def test_phone_unknown_country_falls_back_to_default_regions():
    """Sometimes the country column holds nonsense like Atlantis or just spaces. That
    shouldn't break anything, so we use the default region, and with no default at
    all the number is simply kept as typed."""
    cleaner = PhoneCleaner(default_regions=("IN",))
    assert cleaner.clean_row("9876543210", "Atlantis") == "+919876543210"
    assert cleaner.clean_row("9876543210", "  ") == "+919876543210"
    # No usable country and no default region: unjudgeable, kept as-is.
    assert PhoneCleaner().clean_row("9876543210", "Atlantis") == "9876543210"


def test_phone_clean_value_invalid_returns_none():
    """Text like N/A, a number that is too short, or a random sentence is not a phone
    number and becomes null. If a real number is buried in a sentence, though, we
    are happy to pull it out."""
    cleaner = PhoneCleaner(default_regions=("IN",))

    # 1. Truly malformed strings, missing digits, or arbitrary text drop out safely
    assert cleaner.clean_row("N/A") is None
    assert cleaner.clean_row("98765") is None  # Too short for a valid number
    assert cleaner.clean_row("This is completely random text") is None

    # 🚀 FIX 2: Acknowledge that the engine is powerful enough to extract phone numbers hidden inside text blobs!
    assert cleaner.clean_row("Call me at 9876543210") == "+919876543210"


# ==============================================================================
# 3. NOISE, ANNOTATIONS AND JUNK
# ==============================================================================


@pytest.mark.parametrize(
    "raw",
    [
        "tel:+442079460958",
        "mobile: +44 20 7946 0958",
        "+44 20 7946 0958 (fax)",
        "+44 (0)20 7946 0958 (Mobile)",
        "00 44 20 7946 0958",
        "0044 20 7946 0958",
    ],
)
def test_phone_strips_labels_notes_and_international_prefix(raw):
    """People write numbers with labels like tel: or mobile:, notes like (fax), a (0)
    trunk digit, or 00 instead of a plus. None of that belongs to the number, so
    every variant should land on the same clean +44 value."""
    assert PhoneCleaner().clean_row(raw) == "+442079460958"


def test_phone_label_and_note_are_stripped_with_a_region_too():
    """Label stripping shouldn't only work for plus-prefixed numbers. A local UK mobile
    with a mobile: label in front should also come out clean once a region is set."""
    cleaner = PhoneCleaner(default_regions=("GB",))
    assert cleaner.clean_row("mobile: 07911 123456") == "+447911123456"


def test_phone_transliterates_non_ascii_digits():
    """Digits typed with other scripts, such as Arabic-Indic numerals, are still the
    same digits. We convert them to normal ones first, so the number can be read
    like any other."""
    assert PhoneCleaner().clean_row("٠١٢٣٤٥٦٧٨٩") == "0123456789"
    assert PhoneCleaner(default_regions=("IN",)).clean_row("+٩١ ٩٨٧٦٥ ٤٣٢١٠") == (
        "+919876543210"
    )


@pytest.mark.parametrize("raw", ["abc", "n/a", "N/A", "+", "---"])
def test_phone_without_digits_is_none_even_when_no_region_is_known(raw):
    """If there are no digits at all, as in abc or just a dash, there is nothing that
    could be a phone number. This holds even with no region, where we otherwise keep
    values we can't judge."""
    assert PhoneCleaner().clean_row(raw) is None


@pytest.mark.parametrize(
    "raw",
    [
        "+44 20 7946 0958 / 07911 123456",
        "+44 20 7946 0958; +44 7911 123456",
        "+44 20 7946 0958 or +44 7911 123456",
        "+44 20 7946 0958, +44 7911 123456",
        "n/a / +44 20 7946 0958",
    ],
)
def test_phone_with_several_numbers_in_one_cell_keeps_the_first_valid(raw):
    """Cells often list two numbers, separated by a slash, semicolon, comma or the word
    or. A column can hold only one, so we keep the first valid one and skip junk
    like n/a before it."""
    assert PhoneCleaner(default_regions=("GB",)).clean_row(raw) == "+442079460958"


def test_phone_with_several_numbers_none_valid_is_none():
    """If a cell holds several pieces but none of them is a valid number, there is
    nothing worth keeping. The result is null."""
    assert PhoneCleaner(default_regions=("GB",)).clean_row("abc / 12345") is None


def test_phone_extension_is_dropped_when_the_number_is_valid():
    """Extensions such as ext. 123 or x12 are not part of the phone number itself. We
    drop them and keep the main number."""
    cleaner = PhoneCleaner(default_regions=("GB",))
    assert cleaner.clean_row("020 7946 0958 ext. 123") == "+442079460958"
    assert cleaner.clean_row("+44 20 7946 0958x12") == "+442079460958"


def test_phone_cleaner_strips_html() -> None:
    """Data exported from web pages can wrap the number in tags like bold. We peel the
    markup off first, so the number inside is still found."""
    assert PhoneCleaner().clean_row("<b>+44 121 234 5678</b>") == "+441212345678"


def test_phone_vanity_numbers_and_too_long_digit_strings_are_dropped() -> None:
    """Vanity numbers like 1-800-FLOWERS and absurdly long digit strings are not usable
    numbers. We check this for a few different countries because the answer should
    never depend on the row's country."""
    # The result must not depend on the row's country.
    for country in (None, "Germany", "India"):
        cleaner = PhoneCleaner()
        assert cleaner.clean_row("1-800-FLOWERS", country) is None
        assert cleaner.clean_row("1234567890123456789", country) is None


@pytest.mark.parametrize(
    "raw", ["+22 (521) 234-56789", "+97.150.1234567", "+88 (691) 234-5678"]
)
def test_phone_rejects_a_country_code_split_by_a_separator(raw: str) -> None:
    """If a separator cuts through the country code, for example +22 (521), we can't
    tell what was meant. Guessing might produce a wrong but valid-looking number, so
    we reject it."""
    assert PhoneCleaner().clean_row(raw) is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("+44 (0)7400 123456", "+447400123456"),
        ("+ 44 7400 123456", "+447400123456"),
        ("0044 7400123456", "+447400123456"),
    ],
)
def test_phone_keeps_a_country_code_written_in_one_piece(
    raw: str, expected: str
) -> None:
    """A country code that is written whole is fine even with quirks such as a space
    after the plus, a (0) trunk digit or a leading 0044. These should all normalise
    to the same +44 number."""
    assert PhoneCleaner().clean_row(raw) == expected


def test_phone_clean_strips_emoji():
    """People sometimes put a phone emoji in front of the number. It is only
    decoration, so we ignore it and still read the US number correctly."""
    assert (
        PhoneCleaner(default_regions=("US",)).clean_row("\U0001f4de (415) 555-2671")
        == "+14155552671"
    )
