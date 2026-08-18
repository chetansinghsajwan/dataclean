"""Main pipeline orchestrator for unified cleaners."""

import logging
from collections.abc import Callable, Sequence
from typing import Any

from dataclean.cleaners import Cleaner
from dataclean.col_renamer import ColRenamer
from dataclean.config import config
from dataclean.engine import DataFrame, DataWriter
from dataclean.types import checked

from .assignments import Assignment
from .cleaner_resolver import Resolver
from .dependency_resolver import DependencyResolver
from .entity_extractor import EntityExtractor

PRIMARY = "value"

_logger = logging.getLogger(__name__)


def _is_missing(value: Any) -> bool:
    """Return True for values that engines use to represent absent data: Python's
    None, and float NaN (e.g. pandas' representation of missing cells)."""
    return value is None or value != value  # noqa: PLR0124 (NaN != NaN by design)


@checked
class Pipeline:
    """Resolve unified cleaners and execute them in dependency-safe waves."""

    _cleaners: tuple[Cleaner, ...]
    _column_cleaners: dict[str, Cleaner]
    _context_overrides: dict[str, dict[str, str]]
    _auto_detect: bool
    _resolver: Resolver
    _dependency_resolver: DependencyResolver

    def __init__(
        self,
        cleaners: Sequence[Cleaner] = (),
        column_cleaners: dict[str, Cleaner] | None = None,
        context_overrides: dict[str, dict[str, str]] | None = None,
        auto_detect: bool = True,
    ) -> None:
        self._cleaners = tuple(cleaners)
        self._column_cleaners = column_cleaners or {}
        self._context_overrides = context_overrides or {}
        self._auto_detect = auto_detect
        self._resolver = Resolver(cleaners=self._cleaners)

        extractor = EntityExtractor(words_fn=ColRenamer()._get_words)
        self._dependency_resolver = DependencyResolver(entity_extractor=extractor)

    def fit_transform(self, df: DataFrame | object) -> DataFrame:
        """Clean a DataFrame through the engine abstraction."""

        _logger.info("Starting pipeline with %d cleaner(s)...", len(self._cleaners))
        df = self._wrap_df(df)
        columns = set(df.col_names())
        _logger.debug("Resolving assignments for columns: %s", sorted(columns))
        assignments = self._resolver.resolve(df, columns, self._column_cleaners)

        if not self._auto_detect:
            assignments = tuple(
                assignment for assignment in assignments if assignment.confidence == 1.0
            )

        _logger.info("Resolved %d assignment(s).", len(assignments))
        if _logger.isEnabledFor(logging.DEBUG):
            for assignment in assignments:
                _logger.debug(
                    "Assignment: cleaner=%s roles=%s confidence=%.2f",
                    assignment.cleaner.name,
                    assignment.role_columns,
                    assignment.confidence,
                )

        waves = self._dependency_resolver.resolve(assignments, self._context_overrides)
        _logger.info("Executing %d wave(s)...", len(waves))
        for wave_index, wave in enumerate(waves, start=1):
            _logger.debug(
                "[wave %d/%d] Cleaners: %s",
                wave_index,
                len(waves),
                [assignment.cleaner.name for assignment in wave],
            )
            writers = tuple(self._writer_for(assignment) for assignment in wave)
            df.write_cols(writers)

        _logger.info("Pipeline finished.")
        return df

    def _wrap_df(self, df: Any) -> DataFrame:

        if isinstance(df, DataFrame):
            return df

        for api in config.dataframe_apis:
            if api.supports(df):
                # API classes are expected to be callables that construct a wrapper when given df=df
                return api(df=df)

        raise TypeError(f"Unsupported dataframe type: {type(df)}")

    def _writer_for(self, assignment: Assignment) -> DataWriter:
        cleaner = assignment.cleaner
        read_columns = tuple(assignment.role_columns.values()) + tuple(
            assignment.context_columns.values()
        )
        # Same key order as read_columns above, so position i in read_columns
        # corresponds to position i in ordered_keys.
        ordered_keys = tuple(assignment.role_columns.keys()) + tuple(
            assignment.context_columns.keys()
        )
        outputs = getattr(cleaner, "outputs", None)
        cols = outputs.cols if outputs is not None else ()

        # Determine base primary column for naming
        primary_column = assignment.role_columns.get(
            "value"
        ) or assignment.role_columns.get(
            PRIMARY, next(iter(assignment.role_columns.values()))
        )
        if not primary_column:
            raise ValueError("Scalar cleaners require a 'value' input role")

        if len(cols) == 1:
            # Single-column cleaners overwrite the primary input column in the pipeline
            write_columns = ((primary_column, cols[0].dtype),)
        else:
            write_columns = tuple(
                (f"{primary_column}_{(col.name or str(i))}_cleaned", col.dtype)
                for i, col in enumerate(cols)
            )

        required_keys = {col.key for col in cleaner.inputs.cols if col.required}
        required_positions = tuple(
            i for i, key in enumerate(ordered_keys) if key in required_keys
        )
        output_count = 1 if len(cols) <= 1 else len(cols)

        return DataWriter(
            expr=self._guarded_expr(
                cleaner.clean_row, required_positions, output_count
            ),
            read_cols=read_columns,
            write_cols=write_columns,
        )

    @staticmethod
    def _guarded_expr(
        clean_row: Callable[..., Any],
        required_positions: tuple[int, ...],
        output_count: int,
    ) -> Callable[..., Any]:
        """Wrap a cleaner's clean_row so it is never invoked when a required input is
        missing (None or NaN, e.g. from pandas). Skipping the call keeps engines from
        having to pass real values into cleaners that don't guarantee handling for them,
        and avoids running cleaning logic on rows that can't produce a meaningful result
        anyway."""

        if not required_positions:
            return clean_row

        none_result: Any = None if output_count == 1 else (None,) * output_count

        def guarded(*values: Any) -> Any:
            if any(_is_missing(values[i]) for i in required_positions):
                return none_result
            return clean_row(*values)

        return guarded
