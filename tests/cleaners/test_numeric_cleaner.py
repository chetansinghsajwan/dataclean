import pytest

from dataclean import DataType, NumericCleaner

# ==============================================================================
# 1. CORE METADATA & DATA TYPE HEURISTICS
# ==============================================================================


def test_numeric_cleaner_metadata():
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
    cleaner = NumericCleaner(
        out_format=NumericCleaner.Format.FLOAT, parse_suffixes=True
    )
    assert cleaner.clean_row(input_val) == expected_output


def test_numeric_clean_value_returns_none_on_miss():
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
    assert NumericCleaner().clean_row(input_val) is None


def test_numeric_clean_suffixes_are_on_by_default():
    assert NumericCleaner().clean_row("2.5k") == "2500.0"
    assert NumericCleaner().clean_row("10 K") == "10000.0"
    assert NumericCleaner().clean_row("1.5M") == "1500000.0"
    assert NumericCleaner().clean_row("12 kg") is None
    assert NumericCleaner().clean_row("test") is None


def test_numeric_clean_suffixes_can_be_turned_off():
    cleaner = NumericCleaner(parse_suffixes=False)
    assert cleaner.clean_row("2.5k") is None
    assert cleaner.clean_row("10 K") is None
    assert cleaner.clean_row("2,500") == "2500.0"


# ==============================================================================
# 5. EXACT PARSING AND OUTPUT TYPES
# ==============================================================================


def test_numeric_clean_int_is_exact_and_limited_to_64_bits():
    cleaner = NumericCleaner(out_format=NumericCleaner.Format.INT, precision=None)
    assert cleaner.clean_row("9007199254740993") == "9007199254740993"
    assert cleaner.clean_row("9223372036854775807") == "9223372036854775807"
    assert cleaner.clean_row("9223372036854775808") is None
    assert cleaner.clean_row("-1,500.9") == "-1500"


def test_numeric_clean_default_rounding_is_unchanged():
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
    mostly_missing = ["1,000", "2,500", None, float("nan"), "", "  ", "null", "N/A"]
    assert _score("creditlimit", mostly_missing) > 0.9
    assert _score("whatever", ["1,000", "2,500", "750", "n/a", "-", "inf"]) == 0.7


def test_numeric_detection_uses_quantity_name_hints():
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
    assert _score(column, ["1", "2", "3"]) == 0.0


def test_numeric_detection_does_not_mistake_paid_for_an_id():
    assert _score("paid", ["10", "20", "30"]) > 0.0


def test_numeric_detection_skips_identifier_values():
    assert _score("ref", ["007", "042", "100"]) == 0.0
    assert _score("ref", ["123456789012", "5"]) == 0.0
    unique = [str(n) for n in range(1, 41)]
    assert _score("seq", unique) == 0.0
    repeated = [str(n % 5) for n in range(40)]
    assert _score("seq", repeated) > 0.0


def test_numeric_detection_text_scores_low():
    assert _score("notes", ["alpha", "beta", "gamma"]) == 0.0
    assert _score("notes", []) == 0.0
