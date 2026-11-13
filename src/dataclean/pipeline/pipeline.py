"""Main pipeline orchestrator for unified cleaners."""

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import replace
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
from .exceptions import PipelineConfigError

PRIMARY = "value"

_logger = logging.getLogger(__name__)


def _is_missing(value: Any) -> bool:
    """Return whether a value represents absent data.

    Args:
        value: The value to check.

    Returns:
        True for values that engines use to represent absent data: Python's
        None, and float NaN (e.g. pandas' representation of missing cells).
    """
    return value is None or value != value  # noqa: PLR0124 (NaN != NaN by design)


def _normalize(value: Any) -> Any:
    """Normalize a raw input value to the form cleaners expect.

    Missing values (None, NaN) and strings that are empty or whitespace-only
    become None; other strings are stripped of surrounding whitespace; any
    non-string value is returned unchanged.
    """
    if _is_missing(value):
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


@checked
class Pipeline:
    """Resolve unified cleaners and execute them in dependency-safe waves.

    Given a set of `Cleaner` instances, a `Pipeline` matches them to a
    dataframe's columns (via `Resolver`), resolves any cross-cleaner context
    dependencies and orders execution into waves (via `DependencyResolver`),
    and then runs each wave against the dataframe in turn.

    Attributes:
        _cleaners: The candidate cleaners available to the pipeline.
        _column_cleaners: Explicit column name to cleaner overrides that
            bypass automatic matching for that column.
        _context_overrides: Explicit consumer column to (role name to
            producer column) mappings that disambiguate context role
            resolution.
        _auto_detect: Whether to keep assignments that were auto-matched
            rather than only explicit ones.
        _keep_original: Whether to keep a copy of each column that a cleaner
            overwrites in place, under its name plus ``_original_suffix``.
        _original_suffix: Suffix of the retained original columns.
        _resolver: Resolves dataframe columns to cleaner assignments.
        _dependency_resolver: Resolves context dependencies between
            assignments and orders them into execution waves.
    """

    _cleaners: tuple[Cleaner, ...]
    _column_cleaners: dict[str, Cleaner]
    _context_overrides: dict[str, dict[str, str]]
    _auto_detect: bool
    _keep_original: bool
    _original_suffix: str
    _ignore_cols: frozenset[str]
    _resolver: Resolver
    _dependency_resolver: DependencyResolver

    def __init__(
        self,
        cleaners: Sequence[Cleaner] = (),
        column_cleaners: dict[str, Cleaner] | None = None,
        context_overrides: dict[str, dict[str, str]] | None = None,
        auto_detect: bool = True,
        ignore_cols: Iterable[str] | None = None,
        keep_original: bool = False,
        original_suffix: str = "_uncleaned",
    ) -> None:
        """Initialize the pipeline with its candidate cleaners and options.

        Args:
            cleaners: Candidate cleaners to match against dataframe columns.
                Defaults to an empty tuple.
            column_cleaners: Explicit mapping of column name to the cleaner
                that must handle it, bypassing automatic matching for that
                column. Defaults to None (no explicit overrides).
            context_overrides: Explicit mapping of consumer column name to a
                mapping of context role name to the producer column name that
                should supply it, used to disambiguate automatic context
                resolution. Defaults to None (no explicit overrides).
            auto_detect: Whether to keep automatically matched assignments
                in addition to explicit ones. When False, only explicit
                (``column_cleaners``) assignments are executed.
                Defaults to True.
            ignore_cols: Column names to exclude from cleaner resolution
                entirely, so no cleaner is assigned to them. Defaults to
                None (no columns excluded).
            keep_original: Whether to keep the raw values of every column a
                cleaner overwrites in place, as a copy named after the
                column plus ``original_suffix`` (e.g. ``email_uncleaned``),
                taken before any cleaner runs. Columns that cleaners only
                add new columns for are not copied. Defaults to False.
            original_suffix: Suffix of the retained original columns.
                Defaults to ``"_uncleaned"``.
        """
        self._cleaners = tuple(cleaners)
        self._column_cleaners = column_cleaners or {}
        self._context_overrides = context_overrides or {}
        self._auto_detect = auto_detect
        self._keep_original = keep_original
        self._original_suffix = original_suffix
        self._ignore_cols = frozenset(ignore_cols) if ignore_cols else frozenset()
        self._words_fn = ColRenamer().words
        self._resolver = Resolver(cleaners=self._cleaners, words_fn=self._words_fn)

        extractor = EntityExtractor(words_fn=ColRenamer()._get_words)
        self._dependency_resolver = DependencyResolver(entity_extractor=extractor)

    def fit_transform(self, df: DataFrame | object) -> DataFrame:
        """Clean a DataFrame through the engine abstraction.

        Wraps `df` in a `DataFrame` implementation if needed, resolves
        cleaner assignments for its columns, resolves context dependencies
        and execution order, then executes each resulting wave of cleaners
        against the dataframe in sequence.

        Args:
            df: The dataframe to clean. May be an already-wrapped `DataFrame`
                or a raw dataframe object supported by one of the configured
                engine APIs (see `config.dataframe_apis`).

        Returns:
            The dataframe (wrapped as a `DataFrame`) after all resolved
            cleaners have been applied.

        Raises:
            TypeError: If `df` is not a `DataFrame` and no configured engine
                API supports its raw type.
            MissingRequiredRoleError: If a required context role has no
                producer, or a context override references a column no
                producer of that role writes.
            AmbiguousRoleError: If a required context role has multiple
                producers that cannot be disambiguated.
            CycleDetectedError: If the resolved cleaner dependencies contain
                a cycle.
            PipelineConfigError: If ``keep_original`` is set and a retained
                column's name is already used by another column.
        """

        _logger.info("Starting pipeline with %d cleaner(s)...", len(self._cleaners))
        df = self._wrap_df(df)
        columns = set(df.col_names()) - self._ignore_cols
        _logger.debug("Resolving assignments for columns: %s", sorted(columns))
        assignments = self._resolver.resolve(df, columns, self._column_cleaners)

        if not self._auto_detect:
            assignments = tuple(
                assignment for assignment in assignments if assignment.explicit
            )

        assignments = tuple(
            replace(
                assignment,
                cleaner=assignment.cleaner.fit(
                    df,
                    assignment.role_columns,
                    {
                        role: self._words_fn(column)
                        for role, column in assignment.role_columns.items()
                    },
                ),
            )
            for assignment in assignments
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
        writers_by_wave = tuple(
            tuple(self._writer_for(assignment) for assignment in wave) for wave in waves
        )
        if self._keep_original:
            self._retain_originals(df, writers_by_wave)

        _logger.info("Executing %d wave(s)...", len(waves))
        for wave_index, (wave, writers) in enumerate(
            zip(waves, writers_by_wave, strict=True), start=1
        ):
            _logger.debug(
                "[wave %d/%d] Cleaners: %s",
                wave_index,
                len(waves),
                [assignment.cleaner.name for assignment in wave],
            )
            df.write_cols(writers)

        _logger.info("Pipeline finished.")
        return df

    def _retain_originals(
        self, df: DataFrame, writers_by_wave: tuple[tuple[DataWriter, ...], ...]
    ) -> None:
        """Copy every column the writers overwrite in place, before they run.

        Args:
            df: The dataframe about to be cleaned.
            writers_by_wave: The writers of every wave.

        Raises:
            PipelineConfigError: If a copy's name is already a column, or is
                also written by a cleaner.
        """
        existing = set(df.col_names())
        written = {
            name
            for writers in writers_by_wave
            for w in writers
            for name, _ in w.write_cols
        }
        copies = {
            name: f"{name}{self._original_suffix}"
            for name in sorted(written & existing)
        }
        taken = (existing | written) & set(copies.values())
        if taken:
            raise PipelineConfigError(
                f"Cannot keep originals: column(s) {sorted(taken)} already exist. "
                "Choose a different original_suffix."
            )
        if copies:
            df.copy_cols(copies)

    def _wrap_df(self, df: Any) -> DataFrame:
        """Wrap a raw dataframe in the appropriate configured `DataFrame` API.

        Args:
            df: The dataframe to wrap. If already a `DataFrame`, it is
                returned unchanged.

        Returns:
            A `DataFrame` wrapping `df`.

        Raises:
            TypeError: If `df` is not a `DataFrame` and none of
                `config.dataframe_apis` reports supporting its type.
        """

        if isinstance(df, DataFrame):
            return df

        for api in config.dataframe_apis:
            if api.supports(df):
                # API classes are expected to be callables that construct a wrapper when given df=df
                return api(df=df)

        raise TypeError(f"Unsupported dataframe type: {type(df)}")

    def _writer_for(self, assignment: Assignment) -> DataWriter:
        """Build the `DataWriter` that executes one resolved assignment.

        Determines which raw and context columns to read (in the order the
        cleaner's `clean_row` expects them), derives the output column
        name(s) from the assignment's primary column (overwriting it in
        place for single-output cleaners, or deriving suffixed names for
        multi-output cleaners), and wraps `clean_row` so it is skipped when a
        required input is missing.

        Args:
            assignment: The resolved assignment (cleaner, role columns, and
                context columns) to build a writer for.

        Returns:
            A `DataWriter` describing how to read the assignment's input
            columns, invoke the (guarded) cleaner expression, and write its
            output columns.

        Raises:
            ValueError: If the assignment has no primary ('value') input role
                column, since scalar cleaners require one to derive output
                column names.
        """
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
        primary_column = self._naming_column(assignment)
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
        # clean_row takes one argument per input role, in schema order, while
        # read_columns holds only the roles that found a column. Map each
        # argument to its read position so a missing optional role passes None
        # instead of shifting later values into the wrong parameter.
        arg_positions = tuple(
            ordered_keys.index(col.key) if col.key in ordered_keys else None
            for col in cleaner.inputs.cols
        )

        return DataWriter(
            expr=self._guarded_expr(
                cleaner.clean_row, required_positions, output_count, arg_positions
            ),
            read_cols=read_columns,
            write_cols=write_columns,
        )

    @staticmethod
    def _naming_column(assignment: Assignment) -> str:
        """Return the input column that names (and, for single outputs, receives) the output.

        The primary ``value`` column if the cleaner has one; otherwise the
        first *required* input role's column (e.g. ``address1`` for an
        address cleaner, not whichever optional column happens to be first);
        otherwise the first column.
        """
        role_columns = assignment.role_columns
        if PRIMARY in role_columns:
            return role_columns[PRIMARY]
        for col in assignment.cleaner.inputs.cols:
            if col.required and col.key in role_columns:
                return role_columns[col.key]
        return next(iter(role_columns.values()))

    @staticmethod
    def _guarded_expr(
        clean_row: Callable[..., Any],
        required_positions: tuple[int, ...],
        output_count: int,
        arg_positions: tuple[int | None, ...],
    ) -> Callable[..., Any]:
        """Wrap a cleaner's clean_row to normalize inputs and skip missing rows.

        Every input is normalized first (see :func:`_normalize`): strings are
        stripped, and empty or whitespace-only strings count as missing, so
        cleaners only ever see ``None`` or a non-empty, trimmed string. A row
        with a missing required input is then skipped entirely, which keeps
        engines from passing real values into cleaners that don't guarantee
        handling for them and avoids cleaning rows that can't produce a
        meaningful result.

        Args:
            clean_row: The cleaner's row-cleaning function to guard.
            required_positions: Indices into the values passed to
                `clean_row` that must not be missing after normalization.
            output_count: Number of output values `clean_row` produces, used
                to build the correctly-shaped "missing" result when the call
                is skipped.
            arg_positions: For each `clean_row` argument in order, the index
                of its value among the values passed in, or None when that
                role has no column and the argument is passed as None.

        Returns:
            A callable that normalizes its inputs, returns None (or a tuple
            of Nones matching `output_count`) when any required position is
            missing, and otherwise delegates to `clean_row`.
        """

        none_result: Any = None if output_count == 1 else (None,) * output_count

        # Skips the cleaner when a required input is missing, so cleaners never
        # see None for those inputs, and returns the all-None result instead.
        def guarded(*values: Any) -> Any:
            normalized = tuple(_normalize(value) for value in values)
            if any(normalized[i] is None for i in required_positions):
                return none_result
            return clean_row(
                *(None if i is None else normalized[i] for i in arg_positions)
            )

        return guarded
