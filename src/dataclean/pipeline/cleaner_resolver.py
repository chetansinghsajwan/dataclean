"""Resolve raw dataframe columns to unified cleaner assignments."""

import logging
from collections.abc import Mapping, Sequence

from dataclean.cleaners.cleaner import PRIMARY, Cleaner, ColumnRole
from dataclean.engine.dataframe import DataFrame
from dataclean.pipeline.assignments import Assignment

logger = logging.getLogger(__name__)


class Resolver:
    """Resolve both simple and multi-column cleaners in one constrained-first pass."""

    def __init__(self, cleaners: Sequence[Cleaner]) -> None:
        self._cleaners = tuple(cleaners)

    def resolve(
        self,
        df: DataFrame,
        columns: set[str],
        explicit_mapping: Mapping[str, Cleaner] | None = None,
    ) -> tuple[Assignment, ...]:
        """Return assignments, leaving columns without a confident match untouched."""
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
            self._cleaners,
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
        try:
            if role.detector is not None:
                return role.detector.match_score(df, (column,))
            if role.key == PRIMARY:
                return cleaner.match_score(df, (column,))
        except (AttributeError, TypeError, ValueError) as error:
            logger.debug("Error scoring %s on %s: %s", cleaner.name, column, error)
            return 0.0
        hints = role.name_hints or (role.key,)
        return 0.8 if any(hint.lower() in column.lower() for hint in hints) else 0.0
