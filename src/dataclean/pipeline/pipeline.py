"""Main pipeline orchestrator for unified cleaners."""

from collections.abc import Mapping, Sequence
from typing import Any

from dataclean.cleaners.cleaner import Cleaner
from dataclean.col_renamer import ColRenamer
from dataclean.config import config
from dataclean.engine.dataframe import DataFrame, DataWriter
from dataclean.engine.pandas import PandasDataFrame
from dataclean.engine.pyspark import PySparkDataFrame
from dataclean.pipeline.assignments import Assignment
from dataclean.pipeline.cleaner_resolver import Resolver
from dataclean.pipeline.dependency_resolver import DependencyResolver
from dataclean.pipeline.entity_extractor import EntityExtractor


class Pipeline:
    """Resolve unified cleaners and execute them in dependency-safe waves."""

    def __init__(
        self,
        cleaners: Sequence[Cleaner] = (),
        column_cleaners: Mapping[str, Cleaner] | None = None,
        context_overrides: Mapping[str, Mapping[str, str]] | None = None,
        auto_detect: bool = True,
    ) -> None:
        self._cleaners = tuple(cleaners)
        self._column_cleaners = column_cleaners or {}
        self._context_overrides = context_overrides or {}
        self._auto_detect = auto_detect
        extractor = EntityExtractor(ColRenamer()._get_words)
        self._resolver = Resolver(self._cleaners)
        self._dependency_resolver = DependencyResolver(extractor)

    def fit_transform(self, df: DataFrame | object) -> DataFrame:
        """Clean a DataFrame through the engine abstraction."""
        df = self._wrap_df(df)
        assignments = self._resolver.resolve(
            df,
            set(df.col_names()),
            self._column_cleaners,
        )
        if not self._auto_detect:
            assignments = tuple(
                assignment for assignment in assignments if assignment.confidence == 1.0
            )
        waves = self._dependency_resolver.resolve(assignments, self._context_overrides)
        for wave in waves:
            writers = tuple(self._writer_for(assignment) for assignment in wave)
            df.write_cols(writers)
        return df

    def _wrap_df(self, df: Any) -> DataFrame:

        if isinstance(df, DataFrame):
            return df

        for api in config.dataframe_apis:
            if api.supports(df):
                # API classes are expected to be callables that construct a wrapper when given df=df
                return api(df=df)

        # Fallback to built-in adapters so callers don't need to register them manually
        # (convenience for common engines like pandas/pyspark).
        if PandasDataFrame.supports(df):
            return PandasDataFrame(df=df)
        if PySparkDataFrame.supports(df):
            return PySparkDataFrame(df=df)

        raise TypeError(f"Unsupported dataframe type: {type(df)}")

    def _writer_for(self, assignment: Assignment) -> DataWriter:
        cleaner = assignment.cleaner
        read_columns = tuple(assignment.role_columns.values()) + tuple(
            assignment.context_columns.values()
        )
        schema = cleaner.output_schema()
        if isinstance(schema, tuple):
            write_columns = schema
        else:
            primary_column = assignment.role_columns.get("value")
            if primary_column is None:
                raise ValueError("Scalar cleaners require a 'value' input role")
            write_columns = ((primary_column, schema),)
        return DataWriter(
            expr=cleaner.clean_row, read_cols=read_columns, write_cols=write_columns
        )
