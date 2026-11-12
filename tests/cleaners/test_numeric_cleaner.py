"""Numeric cleaner tests: parsing messy numbers, rounding, suffixes, exact integers and column detection."""

import pytest

from dataclean import DataType, NumericCleaner

# ==============================================================================
# 1. CORE METADATA & DATA TYPE HEURISTICS
# ==============================================================================


def test_numeric_cleaner_metadata():
    """The cleaner should name itself NumericCleaner and, in float mode, expose a single double column. The pipeline uses this to know what type comes out."""
    cleaner_float = NumericCleaner(out_format=NumericCleaner.Format.FLOAT)
    assert cleaner_float.name == "NumericCleaner"
    assert len(cleaner_float.outputs.cols) == 1
    assert cleaner_float.outputs.cols[0].dtype == DataType.DOUBLE


# ==============================================================================
# 2. STANDARD COERCION AND TRANSFORMATION TESTS
# ==============================================================================


@pytest.mark.parametrize(
    "input_val, out_fmt, expected_output",
    [
        # --- Standard Numerical Outputs ---
        ("1500.50", NumericCleaner.Format.FLOAT, "1500.5"),
        ("1500", NumericCleaner.Format.INT, "1500"),
        ("-42.8", NumericCleaner.Format.FLOAT, "-42.8"),
        # --- Delimiter & Noise Purging ---
        ("1,500.50", NumericCleaner.Format.FLOAT, "1500.5"),
        ("₹ 1,500.50", NumericCleaner.Format.FLOAT, "1500.5"),
        ("$10,000", NumericCleaner.Format.INT, "10000"),
        # --- Double Decimal Typo Recovery ---
        ("150..50", NumericCleaner.Format.FLOAT, "150.5"),
        ("15..00.50", NumericCleaner.Format.FLOAT, "15.005"),
    ],
)
def test_numeric_clean_value_standard(input_val, out_fmt, expected_output):
    """A table of messy numbers with stray separators, noise and doubled decimal points goes in. Clean numbers should come out in whichever format was asked for."""
    cleaner = NumericCleaner(out_format=out_fmt)
    assert cleaner.clean_row(input_val) == expected_output


# ==============================================================================
# 3. ADVANCED FEATURE TESTS (PRECISION & SUFFIXES)
# ==============================================================================


@pytest.mark.parametrize(
    "input_val, precision, expected_output",
    [
        ("14.555", 2, "14.56"),
        ("14.554", 2, "14.55"),
        ("100.999", 0, "101.0"),
        ("100.123456", 4, "100.1235"),
    ],
)
def test_numeric_clean_value_precision(input_val, precision, expected_output):
    """Precision decides how many decimals survive. We try a few settings to confirm the result is rounded the way the caller expects."""
    cleaner = NumericCleaner(
        out_format=NumericCleaner.Format.FLOAT, precision=precision
    )
    assert cleaner.clean_row(input_val) == expected_output


@pytest.mark.parametrize(
    "input_val, expected_output",
    [
        ("1.5M", "1500000.0"),
        ("50k", "50000.0"),
        ("$ 2.5 B", "2500000000.0"),
        ("1.25 t", "1250000000000.0"),
        # Fallback ensures non-suffixed values still resolve cleanly
        ("500", "500.0"),
    ],
)
def test_numeric_clean_value_suffixes(input_val, expected_output):
    """With suffix parsing on, shorthand like 2.5k should expand to the full figure. Plain numbers with no suffix must still come through fine."""
    cleaner = NumericCleaner(
        out_format=NumericCleaner.Format.FLOAT, parse_suffixes=True
    )
    assert cleaner.clean_row(input_val) == expected_output


def test_numeric_clean_value_returns_none_on_miss():
    """Words like Unknown are not numbers. The cleaner returns null for them instead of raising, so one odd cell cannot stop a whole run."""
    cleaner = NumericCleaner()
    # Unparseable text sequences safely drop out as None without breaking pipeline ops
    assert cleaner.clean_row("not_a_number") is None
    assert cleaner.clean_row("Unknown") is None


# ==============================================================================
# 4. SEPARATORS, CURRENCY MARKERS AND SIGNS
# ==============================================================================


@pytest.mark.parametrize(
    "input_val, expected_output",
    [
        ("1,234.56", "1234.56"),
        ("1.234,56", "1234.56"),
        ("1.000,50", "1000.5"),
        ("1 234,56", "1234.56"),
        ("1'234.56", "1234.56"),
        ("1_000", "1000.0"),
        ("₹1,23,456.78", "123456.78"),
        ("1.234.567", "1234567.0"),
        ("1,234,567", "1234567.0"),
        ("1,5", "1.5"),
        ("1,50", "1.5"),
        ("0,500", "0.5"),
        ("1,234", "1234.0"),
        (".5", "0.5"),
        ("Rs. 5,000", "5000.0"),
        ("Rs.5,000", "5000.0"),
        ("INR 5000", "5000.0"),
        ("USD 12.50", "12.5"),
        ("€ 1.234,50", "1234.5"),
        ("$ -5", "-5.0"),
        ("-$5", "-5.0"),
        ("(1,234)", "-1234.0"),
        ("($5.50)", "-5.5"),
        ("12.5%", "12.5"),
        ("1e3", "1000.0"),
        ("1.5E-3", "0.002"),
        ("١٢٣", "123.0"),
        ("１２３", "123.0"),
        ("-0", "0.0"),
    ],
)
def test_numeric_clean_separators_currency_and_signs(input_val, expected_output):
    """Real data is full of thousands separators, currency symbols and signs. These are only formatting, so we strip them and keep the number, including its sign."""
    assert NumericCleaner().clean_row(input_val) == expected_output


@pytest.mark.parametrize(
    "input_val",
    [
        "12abc34",
        "0x1F",
        "1/2",
        "1,2,3",
        "12 34",
        "+91 98765",
        "1 2 3",
        "1,234 567",
        "--5",
        "5-3",
        "1234-",
        "12e",
        "12 kg",
        "N/A",
        "NaN",
        "Infinity",
        "1e400",
    ],
)
def test_numeric_clean_not_a_number_gives_none(input_val):
    """Things like phone numbers, ranges, hex and NaN look a bit numeric but are not one number. Guessing would give wrong figures, so each becomes null."""
    assert NumericCleaner().clean_row(input_val) is None


def test_numeric_clean_suffixes_are_on_by_default():
    """Without any setting, 2.5k reads as 2500 and 1.5M as one and a half million. A real unit like kg is not a magnitude, so that one is rejected."""
    assert NumericCleaner().clean_row("2.5k") == "2500.0"
    assert NumericCleaner().clean_row("10 K") == "10000.0"
    assert NumericCleaner().clean_row("1.5M") == "1500000.0"
    assert NumericCleaner().clean_row("12 kg") is None
    assert NumericCleaner().clean_row("test") is None


def test_numeric_clean_suffixes_can_be_turned_off():
    """Some datasets use k for something other than thousand. With suffixes switched off, 2.5k is simply not a number, while 2,500 is still fine."""
    cleaner = NumericCleaner(parse_suffixes=False)
    assert cleaner.clean_row("2.5k") is None
    assert cleaner.clean_row("10 K") is None
    assert cleaner.clean_row("2,500") == "2500.0"


# ==============================================================================
# 5. EXACT PARSING AND OUTPUT TYPES
# ==============================================================================


def test_numeric_clean_int_is_exact_and_limited_to_64_bits():
    """Integers are parsed digit by digit, so a number that a float would round, like 9007199254740993, survives intact. Anything too big for 64 bits becomes null rather than overflowing."""
    cleaner = NumericCleaner(out_format=NumericCleaner.Format.INT, precision=None)
    assert cleaner.clean_row("9007199254740993") == "9007199254740993"
    assert cleaner.clean_row("9223372036854775807") == "9223372036854775807"
    assert cleaner.clean_row("9223372036854775808") is None
    assert cleaner.clean_row("-1,500.9") == "-1500"


def test_numeric_clean_default_rounding_is_unchanged():
    """Out of the box the cleaner rounds to three decimals, and passing no precision keeps every digit. This pins the default so existing users do not see their results shift."""
    cleaner = NumericCleaner()
    assert cleaner.clean_row("3.14159") == "3.142"
    assert cleaner.clean_row("0.0005") == "0.001"
    assert NumericCleaner(precision=None).clean_row("3.14159") == "3.14159"


# ==============================================================================
# 6. DETECTION
# ==============================================================================


def _frame(values):
    """A frame stand-in that feeds ``values`` to the readers it is given."""
    from unittest.mock import MagicMock

    from dataclean import DataFrame

    frame = MagicMock(spec=DataFrame)

    def read_cols(readers):
        for reader in readers:
            for value in values:
                reader.fn(value)

    frame.read_cols.side_effect = read_cols
    return frame


def _score(column, values):
    return NumericCleaner().match_score(_frame(values), (column,))


def test_numeric_detection_ignores_missing_and_placeholder_values():
    """Plenty of cells here are blank, null or N/A. Those are skipped when judging the column, so a mostly empty column of real amounts still counts as numeric."""
    mostly_missing = ["1,000", "2,500", None, float("nan"), "", "  ", "null", "N/A"]
    assert _score("creditlimit", mostly_missing) > 0.9
    assert _score("whatever", ["1,000", "2,500", "750", "n/a", "-", "inf"]) == 0.7


def test_numeric_detection_uses_quantity_name_hints():
    """A name like credit_limit or age suggests an amount, so the column scores full marks. Names that merely contain such letters, like page, only get the ordinary score."""
    values = ["1,000", "2,500", "750"]
    assert _score("credit_limit", values) == 1.0
    assert _score("creditlimit", values) == 1.0
    assert _score("age", values) == 1.0
    assert _score("page", values) == 0.7
    assert _score("misc", values) == 0.7


@pytest.mark.parametrize(
    "column",
    ["contactid", "contact_id", "companyid", "id", "rowguid", "postcode", "zip_code"],
)
def test_numeric_detection_skips_identifier_names(column):
    """Columns called id, postcode or zip_code hold numbers that are really labels. Reformatting them would damage them, so they score zero whatever the values."""
    assert _score(column, ["1", "2", "3"]) == 0.0


@pytest.mark.parametrize(
    "col_name", ["contacttypeid_2", "companyid_3", "user_id_2", "order id 10"]
)
def test_numeric_detection_ignores_a_copy_number_after_an_id_name(col_name):
    """Tools often add a suffix such as _2 when a column name is duplicated. That should not disguise an ID column, so these still score zero."""
    assert _score(col_name, ["1", "2", "3"]) == 0.0


def test_numeric_detection_does_not_mistake_paid_for_an_id():
    """The word paid ends in id but means something else entirely. The ID check has to look at whole words, and a paid column of amounts still counts as numeric."""
    assert _score("paid", ["10", "20", "30"]) > 0.0


def test_numeric_detection_skips_identifier_values():
    """Even with an innocent name, values with leading zeros, very long digit runs or all-unique counters look like IDs. Small repeating numbers are different and still count as real data."""
    assert _score("ref", ["007", "042", "100"]) == 0.0
    assert _score("ref", ["123456789012", "5"]) == 0.0
    unique = [str(n) for n in range(1, 41)]
    assert _score("seq", unique) == 0.0
    repeated = [str(n % 5) for n in range(40)]
    assert _score("seq", repeated) > 0.0


def test_numeric_detection_text_scores_low():
    """A notes column of words, or no values at all, offers nothing to clean as a number. It should score zero."""
    assert _score("notes", ["alpha", "beta", "gamma"]) == 0.0
    assert _score("notes", []) == 0.0


def test_numeric_cleaner_int_format_outputs_long():
    """In int mode the column is declared as a 64-bit long. That matches the exact 64-bit parsing described above."""
    cleaner = NumericCleaner(out_format=NumericCleaner.Format.INT)
    assert cleaner.outputs.cols[0].dtype == DataType.LONG
