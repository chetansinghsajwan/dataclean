from collections.abc import Mapping
from typing import Iterable, override

import numpy as np
import pandas as pd

from dataclean.engine.dataframe import DataFrame


class PandasDataFrame(DataFrame):
    df: pd.DataFrame
    _cols: tuple[str]

    def __init__(self, df: pd.DataFrame):

        self.df = df
        self._cols = tuple(df.columns)

    @override
    def supports(df: any) -> bool:
        return isinstance(df, pd.DataFrame)

    @override
    def cols(self) -> tuple[str]:

        return self._cols

    @override
    def rename_cols(self, rename_map: Mapping[str, str]) -> None:

        self.df.rename(columns=rename_map)
        self._cols = tuple(self.df.columns)

    @override
    def read_cols(self, readers: Iterable[DataFrame.DataReader]):

        for fn, *cols in readers:
            if not cols:
                continue

            # Single column operation -> Fast Element Mapping
            if len(cols) == 1:
                self.df[cols[0]].map(fn)

            # Multi-column operation -> Automatic Multi-Arg Unpacking
            else:
                source_arrays = [self.df[col] for col in cols]
                np.vectorize(fn)(*source_arrays)

    @override
    def add_cols(self, cols: Mapping[str, DataFrame.DataReader]) -> None:

        for new_cols, (fn, *cols) in cols.items():
            if not cols:
                continue

            # Single column operation -> Fast Element Mapping
            if len(cols) == 1:
                self.df[new_cols] = self.df[cols[0]].map(fn)

            # Multi-column operation -> Automatic Multi-Arg Unpacking
            else:
                source_arrays = [self.df[col] for col in cols]
                self.df[new_cols] = np.vectorize(fn)(*source_arrays)

        self._cols = tuple(self.df.columns)

    @override
    def remove_cols(self, cols: Iterable[str]) -> None:
        self.df.drop(columns=cols)
        self._cols = tuple(self.df.columns)
