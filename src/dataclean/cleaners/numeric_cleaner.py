import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import override

from dataclean.cleaners.cleaner import Cleaner
from dataclean.engine.dataframe import DataFrame, DataReader, DataType
from dataclean.types import checked


@checked
@dataclass
class NumericCleaner(Cleaner):
    class Format(StrEnum):
        INT = "int"  # Casts the cleaned value to a strict Python integer
        FLOAT = "float"  # Casts the cleaned value to a standard Python float

    out_format: Format = Format.FLOAT
    precision: int | None = 3  # e.g., Set to 2 for strict financial limits
    parse_suffixes: bool = False  # Set to True to calculate 'K', 'M', 'B', 'T' values

    # Global suffix mapping matrix for rapid lookup
    _SUFFIX_MAP = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}

    @override
    def _outputs(self) -> Cleaner.OutputSchema:
        return Cleaner.OutputSchema(
            cols=(
                Cleaner.OutputSchema.Column(
                    dtype=DataType.INT
                    if self.out_format == NumericCleaner.Format.INT
                    else DataType.FLOAT
                ),
            )
        )

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore

        # Base implementation pipeline guarantees that v arrives non-empty and stripped
        normalized = v.lower()
        multiplier = 1.0

        # 1. Process metric/financial scale suffixes if enabled
        if self.parse_suffixes:
            # Isolates the numeric block from the specific trailing scale character
            suffix_match = re.search(r"([\d\.\-e\+]+)\s*([kmbt])\b", normalized)
            if suffix_match:
                normalized = suffix_match.group(1)
                multiplier = self._SUFFIX_MAP[suffix_match.group(2)]
            else:
                normalized = re.sub(r"[^\d\.\-eE+]", "", normalized)
        else:
            # 2. Standard Noise Purge: Strip everything except digits, decimals, and signs
            normalized = re.sub(r"[^\d\.\-eE+]", "", normalized)

        if not normalized:
            return None

        # 3. Typo Recovery: Collapse multiple accidental decimal points
        parts = normalized.split(".")
        if len(parts) > 2:
            normalized = parts[0] + "." + "".join(parts[1:])

        try:
            # 4. Apply scale math and execute float conversion
            float_val = float(normalized) * multiplier
        except ValueError:
            return None

        # Use Decimal for strict financial base-10 rounding
        if self.precision is not None:
            # Convert the float to a string first to strip out the IEEE 754 microscopic drift
            dec_val = Decimal(str(float_val))
            # Generate the target decimal constraint (e.g., precision 2 -> Decimal('0.01'))
            quantize_format = Decimal("10") ** -self.precision
            # Force standard Half-Up rounding
            float_val = float(dec_val.quantize(quantize_format, rounding=ROUND_HALF_UP))

        match self.out_format:
            case NumericCleaner.Format.INT:
                # Truncates any fractional remnants automatically and return as string
                return str(int(float_val))
            case NumericCleaner.Format.FLOAT:
                # Return normalized float string representation
                return str(float_val)

        return None

    @override
    def match_score(self, df: DataFrame, cols: Iterable[str]) -> float:
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0

        confidence = 0.0
        col_name = cols_tuple[0].lower()

        # 1. Structural Column Name Heuristic (Base 30% Weight)
        if any(
            token in col_name
            for token in ("amount", "price", "count", "quantity", "revenue", "total")
        ):
            confidence += 0.3

        # 2. Stateful Data-Driven Heuristic (70% Weight)
        # We create a stateful tracker to capture execution results from the abstract DataFrame API
        class NumericSampler:
            def __init__(self, cleaner: NumericCleaner, limit: int = 100):
                self.cleaner = cleaner
                self.limit = limit
                self.total = 0
                self.valid = 0

            def __call__(self, val: str | bool | int | float | None) -> None:
                if self.total >= self.limit or val is None:
                    return

                self.total += 1
                # Cast the incoming raw database value to a string and attempt a clean
                if self.cleaner.clean_row(str(val)) is not None:
                    self.valid += 1

        sampler = NumericSampler(self, limit=100)

        # Inject our stateful tracker directly into the engine's read configuration
        reader = DataReader(fn=sampler, cols=(cols_tuple[0],))
        df.read_cols([reader])

        # Calculate the success ratio and apply it to the remaining confidence margin
        if sampler.total > 0:
            ratio = sampler.valid / sampler.total
            confidence += ratio * 0.7

        return min(confidence, 1.0)
