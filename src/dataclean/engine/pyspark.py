from typing import Self
from pydantic import model_validator
from collections.abc import Iterable, Mapping
from typing import Any, override

import pandas as pd
import pyspark.sql as sp
import pyspark.sql.connect.dataframe as spc
import pyspark.sql.functions as spf
import pyspark.sql.types as spt

from dataclean.engine.dataframe import DataFrame, DataReader, DataType, DataWriter


class PySparkDataFrame(DataFrame):
    df: sp.DataFrame | spc.DataFrame
    _cols: tuple[tuple[str, DataType], ...]

    @model_validator(mode="after")
    def _initialize_internal_cache(self) -> Self:
        self._update_cols()
        return self

    @staticmethod
    @override
    def supports(df: Any) -> bool:
        return isinstance(df, (sp.DataFrame, spc.DataFrame))

    @override
    def cols(self) -> tuple[tuple[str, DataType], ...]:
        return self._cols

    @override
    def rename_cols(self, rename_map: Mapping[str, str]):
        self.df = self.df.withColumnsRenamed(rename_map)
        self._update_cols()

    @override
    def read_cols(self, readers: Iterable[DataReader]):
        """
        Executes a fast, read-only iteration over the specified columns
        across cluster partitions without modifying or saving the DataFrame state.
        """

        def process_partition(row_iterator: Iterable[sp.Row]):
            for row in row_iterator:
                for reader in readers:
                    args = [row[col] for col in reader.cols]
                    reader.fn(*args)

        self.df.foreachPartition(process_partition)

    @override
    def write_cols(self, writers: Iterable[DataWriter]) -> None:
        """
        Processes an iterable configuration of DataWriters. Evaluates expressions,
        maps individual arguments dynamically into user callables, and appends or
        overwrites data structures using an optimized vector engine.
        """

        for writer in writers:
            if len(writer.write_cols) == 0:
                continue

            # ==================================================================
            # If expr is a literal (str, int, bool, float, None)
            # ==================================================================
            if not callable(writer.expr):
                self.df = self.df.withColumns(
                    {
                        write_col: spf.lit(writer.expr).cast(write_data_type)
                        for write_col, write_data_type in writer.write_cols
                    }
                )

                continue

            # ==================================================================
            # If expr is a callable, but single column output
            # ==================================================================

            if len(writer.write_cols) == 1:
                write_col, write_type = writer.write_cols[0]
                write_type = self._to_pyspark_data_type(write_type)

                @spf.pandas_udf(write_type)
                def vectorized_writer_wrapper(*args: pd.Series) -> pd.DataFrame:

                    result = list()

                    for row_inputs in zip(*args):
                        res = writer.expr(*row_inputs)
                        result.append(res)

                    return pd.DataFrame(write_type)

                self.df = self.df.withColumn(
                    write_col,
                    vectorized_writer_wrapper(*[spf.col(c) for c in writer.read_cols]),
                )

                continue

            # ==================================================================
            # If expr is a callable (Multi-Output Vector UDF)
            # ==================================================================

            write_schema = spt.StructType(
                [
                    spt.StructField(
                        write_col, self._to_pyspark_data_type(write_type), True
                    )
                    for write_col, write_type in writer.write_cols
                ]
            )

            @spf.pandas_udf(write_schema)
            def vectorized_writer_wrapper(*args: pd.Series) -> pd.DataFrame:

                output_records = {
                    write_col: list() for write_col, _ in writer.write_cols
                }

                for row_inputs in zip(*args):
                    res = writer.expr(*row_inputs)

                    for (new_col, _), val in zip(writer.write_cols, res):
                        output_records[new_col].append(val)

                return pd.DataFrame(output_records)

            # Execute the Vectorized UDF on the target columns. This wraps results inside a temporary struct
            temp_struct_col = "_temp_writer_struct"
            source_column_references = [spf.col(c) for c in writer.read_cols]

            self.df = self.df.withColumn(
                temp_struct_col,
                vectorized_writer_wrapper(*source_column_references),
            )

            # Flatten/Unpack the temporary struct elements back into separate top-level columns instantly
            # Using 'select("*", "struct.*")' handles both additions and native overwrites cleanly
            struct_expansions = [
                spf.col(f"{temp_struct_col}.{write_col}").alias(write_col)
                for write_col, _ in writer.write_cols
            ]

            # Re-select existing columns (excluding the temp struct itself) and merge our expansions
            other_cols = [
                spf.col(c)
                for c in self.df.columns
                if c != temp_struct_col and c not in [nc for nc, _ in writer.write_cols]
            ]
            self.df = self.df.select(*other_cols, *struct_expansions)

        self._update_cols()

    @override
    def remove_cols(self, cols: Iterable[str]):
        self.df = self.df.drop(*cols)
        self._update_cols()

    @override
    def cast_cols(self, cols: Mapping[str, DataType]):
        self.df = self.df.withColumns(
            {
                col: spf.col(col).cast(self._to_pyspark_data_type(data_type))
                for col, data_type in cols.items()
            }
        )

    def _update_cols(self):
        self._cols = tuple(
            (field.name, self._from_pyspark_data_type(field.dataType))
            for field in self.df.schema
        )

    @staticmethod
    def _to_pyspark_data_type(data_type: DataType) -> spt.DataType:
        if data_type == "str":
            return spt.StringType()

        if data_type == "bool":
            return spt.BooleanType()

        if data_type == "int":
            return spt.IntegerType()

        if data_type == "float":
            return spt.FloatType()

        if data_type == "double":
            return spt.DoubleType()

        return spt.StringType()

    @staticmethod
    def _from_pyspark_data_type(data_type: spt.DataType) -> DataType:
        if data_type == spt.StringType():
            return "str"

        if data_type == spt.BooleanType():
            return "bool"

        if data_type == spt.IntegerType():
            return "int"

        if data_type == spt.FloatType():
            return "float"

        if data_type == spt.DoubleType():
            return "double"

        return "str"
