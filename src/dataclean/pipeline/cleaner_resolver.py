"""Resolver for matching columns to BaseCleaner instances."""

import logging
from collections.abc import Mapping, Sequence

from dataclean.cleaners.base_cleaner import BaseCleaner
from dataclean.engine.dataframe import DataFrame
from dataclean.pipeline.assignments import ColumnAssignment

logger = logging.getLogger(__name__)


class CleanerResolver:
    """Resolves base cleaner assignments to columns."""

    def __init__(self, cleaners: Sequence[BaseCleaner]) -> None:
        """Initialize with registered base cleaners."""
        self.cleaners = cleaners

    def resolve(
        self,
        df: DataFrame,
        columns: set[str],
        explicit_mapping: Mapping[str, BaseCleaner] | None = None,
    ) -> tuple[ColumnAssignment, ...]:
        """
        Resolve cleaner assignments to unclaimed columns.

        For each unclaimed column:
        1. Check explicit mapping first (always wins)
        2. Score all cleaners via get_data_type_confidence()
        3. Pick highest score, short-circuit at 1.0
        4. If no confident match, leave column untouched (graceful degradation)

        Args:
            df: DataFrame to analyze for type detection.
            columns: Set of unclaimed column names.
            explicit_mapping: Optional explicit col->cleaner mapping.

        Returns:
            Tuple of column assignments.
        """
        assignments: list[ColumnAssignment] = []
        explicit_mapping = explicit_mapping or {}

        for col in columns:
            # Explicit mapping always wins
            if col in explicit_mapping:
                cleaner = explicit_mapping[col]
                assignments.append(
                    ColumnAssignment(column=col, cleaner=cleaner, confidence=1.0)
                )
                continue

            # Score all cleaners
            best_cleaner = None
            best_score = 0.0

            for cleaner in self.cleaners:
                try:
                    score = cleaner.get_data_type_confidence(df, (col,))
                    if score > best_score:
                        best_score = score
                        best_cleaner = cleaner

                    # Short-circuit at perfect confidence
                    if score >= 1.0:
                        break
                except Exception as e:
                    logger.debug(f"Error scoring {cleaner.name()} on {col}: {e}")
                    continue

            # If we found a confident match, assign it
            if best_cleaner is not None and best_score >= 0.5:
                assignments.append(
                    ColumnAssignment(
                        column=col, cleaner=best_cleaner, confidence=best_score
                    )
                )
            else:
                # Graceful degradation: leave column untouched
                logger.warning(
                    f"No confident cleaner found for column '{col}' "
                    f"(best score: {best_score}). Column will be left untouched."
                )

        return tuple(assignments)
