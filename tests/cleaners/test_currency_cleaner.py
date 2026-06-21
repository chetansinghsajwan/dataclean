from unittest.mock import MagicMock

import pytest

from dataclean.cleaners.currency_cleaner import CurrencyCleaner

# ==============================================================================
# 1. PROPERTIES & CONFIDENCE LOGIC
# ==============================================================================


def test_currency_cleaner_metadata():
    cleaner = CurrencyCleaner()
    assert cleaner.name() == "CurrencyCleaner"
    assert cleaner.output_schema() == "str"


@pytest.mark.parametrize(
    "col_name, expected_confidence",
    [
        ("transaction_currency", 1.0),
        ("curr_code", 1.0),
        ("item_price", 1.0),
        ("total_amount", 1.0),
        ("customer_name", 0.0),
    ],
)
def test_currency_cleaner_confidence(col_name, expected_confidence):
    cleaner = CurrencyCleaner()
    mock_df = MagicMock()
    assert cleaner.get_data_type_confidence(mock_df, (col_name,)) == expected_confidence


# ==============================================================================
# 2. VALUE EXTRACTION AND TRANSFORMATION TESTS
# ==============================================================================


@pytest.mark.parametrize(
    "input_val, out_fmt, expected_output",
    [
        # --- Localized Indian Rupee Variations ---
        ("₹1,500.50", CurrencyCleaner.Format.ISO_CODE, "INR"),
        ("Rs. 1500.50", CurrencyCleaner.Format.ISO_CODE, "INR"),
        ("1500.50 INR", CurrencyCleaner.Format.ISO_CODE, "INR"),
        ("₹1,500.50", CurrencyCleaner.Format.SYMBOL, "₹"),
        ("Rs. 1500.50", CurrencyCleaner.Format.AMOUNT, "1500.50"),
        # --- Western International Currencies ---
        ("$250.00", CurrencyCleaner.Format.ISO_CODE, "USD"),
        ("250 USD", CurrencyCleaner.Format.SYMBOL, "$"),
        ("$10,000", CurrencyCleaner.Format.AMOUNT, "10000.00"),
        ("€45.99", CurrencyCleaner.Format.ISO_CODE, "EUR"),
        ("£10", CurrencyCleaner.Format.AMOUNT, "10.00"),
    ],
)
def test_currency_clean_value_translations(input_val, out_fmt, expected_output):
    cleaner = CurrencyCleaner(out_format=out_fmt)
    assert cleaner.clean_value(input_val) == expected_output


def test_currency_clean_value_returns_none_on_miss():
    cleaner = CurrencyCleaner()
    # Entirely unmapped tokens or random text sequences safely drop out as None
    assert cleaner.clean_value("not_a_currency_symbol") is None
    assert cleaner.clean_value("100.00 XYZ") is None
