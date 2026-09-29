"""Resolve raw dataframe columns to unified cleaner assignments."""

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from dataclean.cleaners import PRIMARY, Cleaner, ColumnRole
from dataclean.engine import DataFrame
from dataclean.types import checked

from .assignments import Assignment

_logger = logging.getLogger(__name__)


@checked
@dataclass(kw_only=True)
class Resolver:
    """Resolve both simple and multi-column cleaners in one constrained-first pass.

    Attributes:
        cleaners: The candidate cleaners to consider when resolving columns.
    """

    cleaners: tuple[Cleaner, ...]

    def resolve(
        self,
        df: DataFrame,
        columns: set[str],
        explicit_mapping: Mapping[str, Cleaner] | None = None,
    ) -> tuple[Assignment, ...]:
        """Resolve dataframe columns to cleaner assignments.

        Explicit mappings are honored first and claim their column outright
        (confidence 1.0). Remaining cleaners are then tried in order of most
        required input columns first, so multi-column (constrained) cleaners
        get first pick of columns before looser, single-column cleaners.
        Columns that no cleaner claims with sufficient confidence are left
        untouched (absent from the returned assignments).

        Args:
            df: The dataframe whose columns are being resolved, passed to
                cleaners' `match_score` for scoring.
            columns: The set of raw column names available to resolve.
            explicit_mapping: Optional mapping of column name to the cleaner
                that must handle it, bypassing scoring for that column.
                Defaults to None (no explicit overrides).

        Returns:
            Tuple of `Assignment` objects, one per column (or column group)
            claimed by a cleaner.
        """
        explicit_mapping = explicit_mapping or {}
        unclaimed = set(columns)
        assignments: list[Assignment] = []

        for column, cleaner in explicit_mapping.items():
            if column not in unclaimed:
                continue
            assignments.append(
                Assignment(
                    cleaner=cleaner, role_columns={PRIMARY: column}, confidence=1.0
                )
            )
            unclaimed.remove(column)

        ordered_cleaners = sorted(
            self.cleaners,
            key=lambda cleaner: sum(col.required for col in cleaner.inputs.cols),
            reverse=True,
        )
        for cleaner in ordered_cleaners:
            cols = cleaner.inputs.cols
            if len(cols) == 1 and cols[0].key == PRIMARY:
                assignments.extend(
                    self._resolve_primary_cleaner(df, unclaimed, cleaner)
                )
                unclaimed -= {
                    assignment.role_columns[PRIMARY]
                    for assignment in assignments
                    if assignment.cleaner is cleaner
                }
                continue

            assignment = self._resolve_multi_role_cleaner(df, unclaimed, cleaner)
            if assignment is not None:
                assignments.append(assignment)
                unclaimed -= set(assignment.role_columns.values())

        return tuple(assignments)

    def _resolve_primary_cleaner(
        self, df: DataFrame, columns: set[str], cleaner: Cleaner
    ) -> tuple[Assignment, ...]:
        """Assign a single-input cleaner to every column it confidently matches.

        Unlike multi-column cleaners, a single-input cleaner is not limited to
        one match: it may be assigned to every remaining column whose score
        meets the acceptance threshold, since matching one column does not
        consume a role needed by another.

        Args:
            df: The dataframe whose columns are being resolved.
            columns: Candidate column names not yet claimed by another
                cleaner.
            cleaner: The single-input cleaner being matched against `columns`.

        Returns:
            Tuple of `Assignment` objects, one per column that scored at
            least 0.5 against `cleaner`.
        """
        assignments: list[Assignment] = []
        for column in sorted(columns):
            score = self._score(df, column, cleaner.inputs.cols[0], cleaner)
            if score >= 0.5:
                assignments.append(
                    Assignment(
                        cleaner=cleaner,
                        role_columns={PRIMARY: column},
                        confidence=score,
                    )
                )
        return tuple(assignments)

    def _resolve_multi_role_cleaner(
        self, df: DataFrame, columns: set[str], cleaner: Cleaner
    ) -> Assignment | None:
        """Assign a multi-input cleaner to its single best-matching set of columns.

        Each input role is matched greedily to the best-scoring column still
        available, and matched columns are removed from consideration so no
        column is claimed by two roles. A required role with no column
        scoring at least 0.5 fails the whole assignment; an optional role in
        that situation is simply left unfilled.

        Args:
            df: The dataframe whose columns are being resolved.
            columns: Candidate column names not yet claimed by another
                cleaner.
            cleaner: The multi-input cleaner being matched against `columns`.

        Returns:
            An `Assignment` with one column per matched role, or None if a
            required role could not be matched or no role was filled at all.
        """
        role_columns: dict[str, str] = {}
        scores: list[float] = []
        available = set(columns)
        for col in cleaner.inputs.cols:
            best_column, best_score = self._best_match(df, available, col, cleaner)
            if best_column is None or best_score < 0.5:
                if col.required:
                    return None
                continue
            role_columns[col.key] = best_column
            scores.append(best_score)
            available.remove(best_column)

        if not role_columns:
            return None
        return Assignment(
            cleaner=cleaner,
            role_columns=role_columns,
            confidence=sum(scores) / len(scores),
        )

    def _best_match(
        self, df: DataFrame, columns: set[str], role: ColumnRole, cleaner: Cleaner
    ) -> tuple[str | None, float]:
        """Find the highest-scoring column for a single input role.

        Args:
            df: The dataframe whose columns are being resolved.
            columns: Candidate column names to score against `role`.
            role: The input role (from `cleaner.inputs.cols`) to match.
            cleaner: The cleaner that declares `role`, used for scoring.

        Returns:
            A tuple of `(best_column, best_score)`. `best_column` is None (with
            score 0.0) if `columns` is empty or every candidate scored 0.0.
        """
        best_column: str | None = None
        best_score = 0.0
        for column in sorted(columns):
            score = self._score(df, column, role, cleaner)
            if score > best_score:
                best_column, best_score = column, score
        return best_column, best_score

    def _score(
        self, df: DataFrame, column: str, role: ColumnRole, cleaner: Cleaner
    ) -> float:
        """Score how well a column matches a single input role.

        A role with an explicit `detector` cleaner defers to that detector's
        own `match_score`. A primary (`PRIMARY`) role defers to the owning
        cleaner's `match_score`. Any other role falls back to a name-hint
        match: 0.8 if the role's key or any of its `name_hints` appears in the
        column name (case-insensitively), otherwise 0.0.

        Args:
            df: The dataframe whose columns are being resolved.
            column: The candidate column name to score.
            role: The input role being matched.
            cleaner: The cleaner that declares `role`.

        Returns:
            A confidence score in the range 0.0-1.0. Returns 0.0 if scoring
            the cleaner raises `AttributeError`, `TypeError`, or `ValueError`.
        """
        try:
            if role.detector is not None:
                return role.detector.match_score(df, (column,))
            if role.key == PRIMARY:
                return cleaner.match_score(df, (column,))

        except (AttributeError, TypeError, ValueError) as error:
            _logger.debug("Error scoring %s on %s: %s", cleaner.name, column, error)
            return 0.0

        hints = role.name_hints or (role.key,)
        return 0.8 if any(hint.lower() in column.lower() for hint in hints) else 0.0
