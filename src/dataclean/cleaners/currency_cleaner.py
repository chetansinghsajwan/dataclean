from decimal import Decimal
from enum import StrEnum
from typing import override

from price_parser import Price

from dataclean.cleaners.base_cleaner import BaseCleaner
from dataclean.engine.dataframe import DataFrame, DataType


class CurrencyCleaner(BaseCleaner, frozen=True):
    class Format(StrEnum):
        AMOUNT = "amount"  # Returns clean numeric string float: "1500.50"
        SYMBOL = "symbol"  # Returns the raw isolated currency token: "₹" or "$"

        # Returns simple mapped codes for major currencies: "INR", "USD"
        ISO_CODE = "iso_code"

    out_format: Format = Format.AMOUNT

    # Safe internal fallback mapping dictionary for common currency symbols to ISO codes
    _COMMON_ISO_MAP: dict[str, str] = {
        "₹": "INR",
        "rs": "INR",
        "rs.": "INR",
        "$": "USD",
        "usd": "USD",
        "€": "EUR",
        "eur": "EUR",
        "£": "GBP",
        "gbp": "GBP",
    }

    @override
    def name(self) -> str:
        return "CurrencyCleaner"

    @override
    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]:
        return "str"

    def _parse(self, v: str) -> tuple[Decimal | None, str | None]:
        parsed = Price.fromstring(v)
        return parsed.amount, parsed.currency

    @override
    def clean_value(self, v: str) -> str | None:

        amount, currency_symbol = self._parse(v)

        match self.out_format:
            case CurrencyCleaner.Format.AMOUNT:
                if amount is None:
                    return None
                # Enforce standard two-decimal financial precision string formatting
                return f"{float(amount):.2f}"

            case CurrencyCleaner.Format.SYMBOL:
                return currency_symbol if currency_symbol else None

            case CurrencyCleaner.Format.ISO_CODE:
                if not currency_symbol:
                    return None
                normalized_symbol = currency_symbol.strip().lower()
                # Direct check against lookup matrix, default back to uppercase raw symbol if missing
                return self._COMMON_ISO_MAP.get(
                    normalized_symbol, currency_symbol.upper()
                )

        return None

    @override
    def get_data_type_confidence(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        if not cols:
            return 0.0
        col_name = cols[0].lower()
        if any(
            token in col_name for token in ("price", "amount", "currency", "curr", "fx")
        ):
            return 1.0
        return 0.0
