import pytest

from dataclean.cleaners.numeric_cleaner import NumericCleaner

# ==============================================================================
# 1. CORE METADATA & DATA TYPE HEURISTICS
# ==============================================================================


def test_numeric_cleaner_metadata():
    cleaner_float = NumericCleaner(out_format=NumericCleaner.Format.FLOAT)
    assert cleaner_float.name() == "NumericCleaner"
    assert cleaner_float.output_schema() == "float"


# ==============================================================================
# 2. STANDARD COERCION AND TRANSFORMATION TESTS
# ==============================================================================


@pytest.mark.parametrize(
    "input_val, out_fmt, expected_output",
    [
        # --- Standard Numerical Outputs ---
        ("1500.50", NumericCleaner.Format.FLOAT, 1500.5),
        ("1500", NumericCleaner.Format.INT, 1500),
        ("-42.8", NumericCleaner.Format.FLOAT, -42.8),
        # --- Delimiter & Noise Purging ---
        ("1,500.50", NumericCleaner.Format.FLOAT, 1500.5),
        ("₹ 1,500.50", NumericCleaner.Format.FLOAT, 1500.5),
        ("$10,000", NumericCleaner.Format.INT, 10000),
        # --- Double Decimal Typo Recovery ---
        ("150..50", NumericCleaner.Format.FLOAT, 150.5),
        ("15..00.50", NumericCleaner.Format.FLOAT, 15.005),
    ],
)
def test_numeric_clean_value_standard(input_val, out_fmt, expected_output):
    cleaner = NumericCleaner(out_format=out_fmt)
    assert cleaner.clean_value(input_val) == expected_output


# ==============================================================================
# 3. ADVANCED FEATURE TESTS (PRECISION & SUFFIXES)
# ==============================================================================


@pytest.mark.parametrize(
    "input_val, precision, expected_output",
    [
        ("14.555", 2, 14.56),
        ("14.554", 2, 14.55),
        ("100.999", 0, 101.0),
        ("100.123456", 4, 100.1235),
    ],
)
def test_numeric_clean_value_precision(input_val, precision, expected_output):
    cleaner = NumericCleaner(
        out_format=NumericCleaner.Format.FLOAT, precision=precision
    )
    assert cleaner.clean_value(input_val) == expected_output


@pytest.mark.parametrize(
    "input_val, expected_output",
    [
        ("1.5M", 1500000.0),
        ("50k", 50000.0),
        ("$ 2.5 B", 2500000000.0),
        ("1.25 t", 1250000000000.0),
        # Fallback ensures non-suffixed values still resolve cleanly
        ("500", 500.0),
    ],
)
def test_numeric_clean_value_suffixes(input_val, expected_output):
    cleaner = NumericCleaner(
        out_format=NumericCleaner.Format.FLOAT, parse_suffixes=True
    )
    assert cleaner.clean_value(input_val) == expected_output


def test_numeric_clean_value_returns_none_on_miss():
    cleaner = NumericCleaner()
    # Unparseable text sequences safely drop out as None without breaking pipeline ops
    assert cleaner.clean_value("not_a_number") is None
    assert cleaner.clean_value("Unknown") is None
