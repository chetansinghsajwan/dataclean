"""Main pipeline orchestrator for data cleaning."""

import logging
from collections.abc import Mapping, Sequence

from dataclean.cleaners.base_cleaner import BaseCleaner, CleanContext
from dataclean.cleaners.group_cleaner import GroupCleaner
from dataclean.col_renamer import ColRenamer
from dataclean.engine.dataframe import DataFrame
from dataclean.pipeline.assignments import ColumnAssignment, GroupAssignment
from dataclean.pipeline.cleaner_resolver import CleanerResolver
from dataclean.pipeline.dependency_resolver import DependencyResolver
from dataclean.pipeline.entity_extractor import EntityExtractor
from dataclean.pipeline.group_cleaner_resolver import GroupCleanerResolver

logger = logging.getLogger(__name__)


class Pipeline:
    """Orchestrates cleaner resolution and execution."""

    def __init__(
        self,
        cleaners: Sequence[BaseCleaner | GroupCleaner] = (),
        column_cleaners: Mapping[str, BaseCleaner] | None = None,
        context_overrides: Mapping[str, Mapping[str, str]] | None = None,
        auto_detect: bool = True,
    ) -> None:
        """
        Initialize pipeline with cleaners.

        Args:
            cleaners: Registered cleaners (both BaseCleaner and GroupCleaner).
            column_cleaners: Explicit column -> cleaner mapping (overrides auto-detect).
            context_overrides: Explicit context role overrides for cleaners.
            auto_detect: If True, auto-detect cleaners for remaining columns.
        """
        self.column_cleaners = column_cleaners or {}
        self.context_overrides = context_overrides or {}
        self.auto_detect = auto_detect

        # Separate cleaners by type
        self.base_cleaners: list[BaseCleaner] = []
        self.group_cleaners: list[GroupCleaner] = []

        for cleaner in cleaners:
            if isinstance(cleaner, GroupCleaner):
                self.group_cleaners.append(cleaner)
            elif isinstance(cleaner, BaseCleaner):
                self.base_cleaners.append(cleaner)

        # Initialize resolvers
        col_renamer = ColRenamer()
        self._entity_extractor = EntityExtractor(col_renamer._get_words)
        self._group_resolver = GroupCleanerResolver(self.group_cleaners)
        self._cleaner_resolver = CleanerResolver(self.base_cleaners)
        self._dependency_resolver = DependencyResolver(self._entity_extractor)

    def fit_transform(self, df: DataFrame | object) -> DataFrame:
        """
        Analyze and clean a dataframe.

        Args:
            df: DataFrame to clean (or compatible object).

        Returns:
            Cleaned DataFrame with transformed columns.

        Raises:
            PipelineConfigError: If configuration is invalid.
        """
        # Convert to DataFrame if needed
        if not isinstance(df, DataFrame):
            # Try auto-detection based on type
            from dataclean.engine.pandas import PandasDataFrame
            from dataclean.engine.pyspark import PysparkDataFrame

            try:
                import pandas

                if isinstance(df, pandas.DataFrame):
                    df = PandasDataFrame(df)
            except ImportError:
                pass

            try:
                import pyspark.sql

                if isinstance(df, pyspark.sql.DataFrame):
                    df = PysparkDataFrame(df)
            except ImportError:
                pass

        if not isinstance(df, DataFrame):
            raise TypeError(
                f"Unsupported dataframe type: {type(df)}. "
                f"Expected DataFrame or pandas/pyspark dataframe."
            )

        # Phase 0-1: Resolve group cleaners
        available_cols = set(df.columns())
        group_assignments = self._group_resolver.resolve(available_cols)
        claimed_cols = set()
        for assignment in group_assignments:
            claimed_cols.update(assignment.role_columns.values())

        # Phase 2: Resolve base cleaners for remaining columns
        unclaimed_cols = available_cols - claimed_cols
        column_assignments = self._cleaner_resolver.resolve(
            df, unclaimed_cols, self.column_cleaners
        )

        # Phase 3-4: Resolve dependencies and build execution plan
        execution_waves = self._dependency_resolver.resolve(
            column_assignments, group_assignments, self.context_overrides
        )

        # Phase 5: Execute waves
        return self._apply(df, execution_waves, available_cols)

    def _apply(
        self,
        df: DataFrame,
        execution_waves: tuple[tuple[ColumnAssignment | GroupAssignment, ...], ...],
        original_cols: set[str],
    ) -> DataFrame:
        """
        Execute cleaning waves and return cleaned dataframe.

        Args:
            df: Original dataframe.
            execution_waves: Topologically sorted execution waves.
            original_cols: Original column names for cleanup.

        Returns:
            Cleaned dataframe with intermediate columns dropped.
        """
        # Track which columns are outputs from cleaners (to keep)
        output_cols = set()

        # Execute each wave
        for wave in execution_waves:
            for assignment in wave:
                if isinstance(assignment, ColumnAssignment):
                    output_cols.add(assignment.column)
                    # Apply base cleaner
                    df = self._apply_base_cleaner(df, assignment, output_cols)
                elif isinstance(assignment, GroupAssignment):
                    # Apply group cleaner
                    new_cols = [name for name, _ in assignment.cleaner.output_schema()]
                    output_cols.update(new_cols)
                    df = self._apply_group_cleaner(df, assignment, new_cols)

        # Drop original uncleaned columns, keep only cleaned outputs
        cols_to_drop = original_cols - output_cols
        for col in cols_to_drop:
            if col in df.columns():
                df = df.drop_column(col)

        return df

    def _apply_base_cleaner(
        self,
        df: DataFrame,
        assignment: ColumnAssignment,
        output_cols: set[str],
    ) -> DataFrame:
        """Apply a base cleaner to a single column."""
        cleaner = assignment.cleaner
        col_name = assignment.column

        # Get the output schema
        output_schema = cleaner.output_schema()

        # Apply cleaner to each value
        cleaned_data = []
        for idx in range(df.row_count()):
            value = df.get_value(idx, col_name)

            # Build context if needed
            context = None
            context_reqs = cleaner.context_requests()
            if context_reqs:
                context_values = {}
                for ctx_req in context_reqs:
                    # Find the producer column for this role
                    # (simplified: assume it's in output_cols)
                    role_cols = [c for c in output_cols if c.endswith(ctx_req.role)]
                    if role_cols:
                        ctx_val = df.get_value(idx, role_cols[0])
                        context_values[ctx_req.role] = ctx_val
                context = CleanContext(values=context_values)

            # Clean value
            result = cleaner.clean_value(value, context)
            cleaned_data.append(result)

        # Add cleaned column(s)
        if isinstance(output_schema, tuple):
            # For split components, add each as separate column
            for i, (output_col, _) in enumerate(output_schema):
                col_data = [
                    row[i] if isinstance(row, tuple) else row for row in cleaned_data
                ]
                df = df.with_column(output_col, col_data)
        else:
            df = df.with_column(col_name, cleaned_data)

        return df

    def _apply_group_cleaner(
        self,
        df: DataFrame,
        assignment: GroupAssignment,
        output_cols_list: list[str],
    ) -> DataFrame:
        """Apply a group cleaner to multiple columns."""
        cleaner = assignment.cleaner
        role_columns = assignment.role_columns

        # Collect values for each row
        cleaned_rows = []
        for idx in range(df.row_count()):
            row_values = {}
            for role_key, col_name in role_columns.items():
                value = df.get_value(idx, col_name)
                row_values[role_key] = value

            # Clean row
            result = cleaner.clean_row(row_values)
            cleaned_rows.append(result)

        # Add output columns
        output_schema = cleaner.output_schema()
        for i, (output_col, _) in enumerate(output_schema):
            col_data = [row[i] if row else None for row in cleaned_rows]
            df = df.with_column(output_col, col_data)

        return df
