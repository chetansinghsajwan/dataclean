from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, override

import numpy as np
import pandas as pd

from dataclean import DataFrame, DataReader, DataType, DataWriter
from dataclean.types import checked


def _stringify(value: Any) -> str | None:
    """Normalize a raw pandas cell value to the str | None contract cleaners expect.

    pandas represents missing data as None or float NaN depending on dtype; both
    are treated as missing here rather than stringified into "nan"/"None".
    """
    if value is None or (isinstance(value, float) and value != value):
        return None
    return str(value)


@checked
@dataclass
class PandasDataFrame(DataFrame):
    df: pd.DataFrame
    _cols: tuple[tuple[str, DataType], ...] = ()

    def __post_init__(self):
        self._update_cols()

    @staticmethod
    @override
    def supports(df: Any) -> bool:
        return isinstance(df, pd.DataFrame)

    @override
    def cols(self) -> tuple[tuple[str, DataType], ...]:
        return self._cols

    @override
    def rename_cols(self, rename_map: Mapping[str, str]) -> None:
        self.df = self.df.rename(columns=rename_map)
        self._update_cols()

    @override
    def read_cols(self, readers: Iterable[DataReader]) -> None:
        for reader in readers:
            if not reader.cols:
                continue

            # Single column operation -> Fast Element Mapping
            if len(reader.cols) == 1:
                self.df[reader.cols[0]].map(reader.fn)

            # Multi-column operation -> Automatic Multi-Arg Unpacking via Vectorization
            else:
                source_arrays = [self.df[col].to_numpy() for col in reader.cols]
                np.vectorize(reader.fn)(*source_arrays)

    @override
    def write_cols(self, writers: Iterable[DataWriter]) -> None:
        for writer in writers:
            if not writer.write_cols:
                continue

            # Destination Column Layout Names
            dest_col_names = [name for name, _ in writer.write_cols]

            # --- SCENARIO A: Expression is a CONSTANT LITERAL ---
            if not callable(writer.expr):
                for name, _ in writer.write_cols:
                    self.df[name] = writer.expr

            # --- SCENARIO B: Expression is a CALLABLE FUNCTION ---
            else:
                expr = self._stringified_expr(writer.expr)
                # 1. Single Input Column Tracking
                if len(writer.read_cols) == 1:
                    computed_series = self.df[writer.read_cols[0]].map(expr)
                # 2. Multi Input Column Tracking via Numpy Vectorization
                else:
                    source_arrays = [
                        self.df[col].to_numpy() for col in writer.read_cols
                    ]
                    computed_series = np.vectorize(expr)(*source_arrays)

                # Unpack results into destination columns depending on output count
                if len(writer.write_cols) == 1:
                    self.df[dest_col_names[0]] = computed_series
                else:
                    # If multiple destination columns exist, the callable is expected to return
                    # an iterable tuple/list. Convert it cleanly to a DataFrame row sequence.
                    unpacked_df = pd.DataFrame(
                        list(computed_series),
                        index=self.df.index,
                        columns=pd.Index(dest_col_names),
                    )
                    for col_name in dest_col_names:
                        self.df[col_name] = unpacked_df[col_name]

            # Enforce the strict destination data types requested by DataWriter mapping
            type_casting_map = {
                name: self._to_pandas_data_type(dt) for name, dt in writer.write_cols
            }
            self.df = self.df.astype(type_casting_map)

        self._update_cols()

    @staticmethod
    def _stringified_expr(expr: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap a cleaner callable so every argument is normalized via _stringify
        before invocation, matching the str | None contract cleaners expect."""

        def wrapped(*args: Any) -> Any:
            return expr(*(_stringify(arg) for arg in args))

        return wrapped

    @override
    def remove_cols(self, cols: Iterable[str]) -> None:
        self.df = self.df.drop(columns=cols)
        self._update_cols()

    @override
    def cast_cols(self, cols: Mapping[str, DataType]) -> None:
        type_casting_map = {
            name: self._to_pandas_data_type(dt) for name, dt in cols.items()
        }
        self.df = self.df.astype(type_casting_map)
        self._update_cols()

    def _update_cols(self) -> None:
        """
        Constructs your private tuple[tuple[str, DataType], ...] cache mapping.
        """

        self._cols = tuple(
            (str(col_name), self._from_pandas_data_type(dtype))
            for col_name, dtype in self.df.dtypes.items()
        )

    def _to_pandas_data_type(self, dt: DataType) -> Any:
        """
        Maps your framework string Literals to native NumPy/Pandas type handles.
        """

        mapping: dict[DataType, Any] = {
            DataType.STR: object,
            DataType.BOOL: bool,
            DataType.INT: np.int64,
            DataType.FLOAT: np.float64,
            DataType.DOUBLE: np.float64,
        }
        return mapping[dt]

    def _from_pandas_data_type(self, dtype: Any) -> DataType:
        """
        Converts native Pandas/NumPy type schemas back to your framework string Literals.
        """

        dtype_str = str(dtype)
        if "int" in dtype_str:
            return DataType.INT
        elif "float" in dtype_str or "double" in dtype_str:
            return DataType.FLOAT
        elif "bool" in dtype_str:
            return DataType.BOOL
        return DataType.STR

    @override
    def group_by(self, cols: Iterable[str]) -> "PandasDataFrame":
        cols_list = list(cols)
        result_df = self.df.groupby(cols_list, as_index=False).first()
        return PandasDataFrame(df=result_df)

    @override
    def agg(
        self, cols: Mapping[str, Callable] | Iterable[Callable] | Callable
    ) -> "PandasDataFrame":
        if isinstance(cols, Mapping):
            # Convert mapped aggregators to apply to selected columns
            result_df = self.df.agg(cols)
        else:
            result_df = self.df.agg(cols)
        # Ensure result is a DataFrame
        if not isinstance(result_df, pd.DataFrame):
            result_df = pd.DataFrame([result_df])
        return PandasDataFrame(df=result_df)

    @override
    def distinct(self, cols: Iterable[str] | None = None) -> "PandasDataFrame":
        if cols is None:
            result_df = self.df.drop_duplicates()
        else:
            cols_list = list(cols)
            result_df = self.df.drop_duplicates(subset=cols_list)
        return PandasDataFrame(df=result_df.reset_index(drop=True))

    @override
    def count(self) -> int:
        return len(self.df)

    @override
    def collect(self) -> list[tuple[Any, ...]]:
        return [tuple(row) for row in self.df.values]

    @override
    def select(self, cols: str | Iterable[str]) -> "PandasDataFrame":
        if isinstance(cols, str):
            cols_list = [cols]
        else:
            cols_list = list(cols)
        result_df = self.df[cols_list]
        return PandasDataFrame(df=result_df)

    @override
    def strip(self, cols: str | Iterable[str] | None = None) -> "PandasDataFrame":
        result_df = self.df.copy()
        if cols is None:
            cols_to_strip = result_df.columns
        else:
            cols_to_strip = [cols] if isinstance(cols, str) else list(cols)

        for col in cols_to_strip:
            if col in result_df.columns:
                result_df[col] = result_df[col].apply(
                    lambda x: x.strip() if isinstance(x, str) else x
                )
        return PandasDataFrame(df=result_df)

    @override
    def nullif(self, cols: str | Iterable[str] | None = None) -> "PandasDataFrame":
        result_df = self.df.copy()
        if cols is None:
            cols_to_nullif = result_df.columns
        else:
            cols_to_nullif = [cols] if isinstance(cols, str) else list(cols)

        for col in cols_to_nullif:
            if col in result_df.columns:
                result_df[col] = result_df[col].apply(
                    lambda x: None if isinstance(x, str) and x == "" else x
                )
        return PandasDataFrame(df=result_df)

    @override
    def order_by(
        self, cols: str | Iterable[str], desc: bool = False
    ) -> "PandasDataFrame":
        if isinstance(cols, str):
            cols_list = [cols]
        else:
            cols_list = list(cols)
        result_df = self.df.sort_values(by=cols_list, ascending=not desc)
        return PandasDataFrame(df=result_df.reset_index(drop=True))

    @override
    def limit(self, n: int) -> "PandasDataFrame":
        result_df = self.df.head(n)
        return PandasDataFrame(df=result_df.reset_index(drop=True))

    @override
    def filter_null(self, cols: str | Iterable[str] | None = None) -> "PandasDataFrame":
        result_df = self.df.copy()
        if cols is None:
            result_df = result_df.dropna()
        else:
            cols_to_filter = [cols] if isinstance(cols, str) else list(cols)
            result_df = result_df.dropna(subset=cols_to_filter)
        return PandasDataFrame(df=result_df.reset_index(drop=True))
