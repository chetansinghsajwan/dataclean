from typing import Self
from pydantic import model_validator
from collections.abc import Mapping
from typing import Any, Iterable, override

import numpy as np
import pandas as pd

from pydantic import PrivateAttr

from dataclean.engine.dataframe import DataFrame, DataReader, DataType, DataWriter


class PandasDataFrame(DataFrame):
    df: pd.DataFrame
    _cols: tuple[tuple[str, DataType], ...] = PrivateAttr(default_factory=tuple)

    @model_validator(mode="after")
    def _initialize(self) -> Self:
        self._update_cols()
        return self

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
                # 1. Single Input Column Tracking
                if len(writer.read_cols) == 1:
                    computed_series = self.df[writer.read_cols[0]].map(writer.expr)
                # 2. Multi Input Column Tracking via Numpy Vectorization
                else:
                    source_arrays = [
                        self.df[col].to_numpy() for col in writer.read_cols
                    ]
                    computed_series = np.vectorize(writer.expr)(*source_arrays)

                # Unpack results into destination columns depending on output count
                if len(writer.write_cols) == 1:
                    self.df[dest_col_names[0]] = computed_series
                else:
                    # If multiple destination columns exist, the callable is expected to return
                    # an iterable tuple/list. Convert it cleanly to a DataFrame row sequence.
                    unpacked_df = pd.DataFrame(
                        list(computed_series),
                        index=self.df.index,
                        columns=dest_col_names,
                    )
                    for col_name in dest_col_names:
                        self.df[col_name] = unpacked_df[col_name]

            # Enforce the strict destination data types requested by DataWriter mapping
            type_casting_map = {
                name: self._to_pandas_data_type(dt) for name, dt in writer.write_cols
            }
            self.df = self.df.astype(type_casting_map)

        self._update_cols()

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
            "str": object,
            "bool": bool,
            "int": np.int64,
            "float": np.float64,
            "double": np.float64,
        }
        return mapping[dt]

    def _from_pandas_data_type(self, dtype: Any) -> DataType:
        """
        Converts native Pandas/NumPy type schemas back to your framework string Literals.
        """

        dtype_str = str(dtype)
        if "int" in dtype_str:
            return "int"
        elif "float" in dtype_str or "double" in dtype_str:
            return "float"
        elif "bool" in dtype_str:
            return "bool"
        return "str"
