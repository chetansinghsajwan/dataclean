"""Resolver for matching columns to GroupCleaner roles."""

import logging
from collections.abc import Sequence

from dataclean.cleaners.group_cleaner import ColumnRole, GroupCleaner
from dataclean.pipeline.assignments import GroupAssignment

logger = logging.getLogger(__name__)


class GroupCleanerResolver:
    """Resolves group cleaner assignments by matching columns to group roles."""

    def __init__(self, cleaners: Sequence[GroupCleaner]) -> None:
        """Initialize with registered group cleaners."""
        self.cleaners = cleaners

    def resolve(self, columns: set[str]) -> tuple[GroupAssignment, ...]:
        """
        Resolve group cleaner assignments from available columns.

        For each group cleaner, attempts to match all required roles.
        Once all required roles are matched above threshold, claims those columns
        and removes them from the unclaimed pool.

        Args:
            columns: Set of unclaimed column names.

        Returns:
            Tuple of group assignments in priority order.

        Raises:
            GroupCleanerResolutionError: If required roles cannot be matched.
        """
        assignments: list[GroupAssignment] = []
        unclaimed = set(columns)

        for cleaner in self.cleaners:
            roles = cleaner.input_roles()
            role_columns: dict[str, str] = {}
            role_scores: dict[str, float] = {}

            # Phase 0: Score every unclaimed column against each role
            for role in roles:
                best_col = None
                best_score = 0.0

                for col in unclaimed:
                    score = self._score_column_for_role(col, role)
                    if score > best_score:
                        best_score = score
                        best_col = col

                if best_col is not None:
                    role_columns[role.key] = best_col
                    role_scores[role.key] = best_score

            # Phase 1: Check if all required roles are matched above threshold
            required_matched = all(
                role.key in role_columns and role_scores[role.key] >= 0.5
                for role in roles
                if role.required
            )

            if required_matched:
                confidence = cleaner.group_confidence(role_scores)
                assignments.append(
                    GroupAssignment(
                        cleaner=cleaner,
                        role_columns=role_columns,
                        confidence=confidence,
                    )
                )
                # Remove claimed columns from unclaimed pool
                unclaimed -= set(role_columns.values())

        return tuple(assignments)

    def _score_column_for_role(self, column: str, role: ColumnRole) -> float:
        """
        Score a column against a role using detector confidence or name hints.

        Args:
            column: Column name to score.
            role: Role to match against.

        Returns:
            Confidence score (0.0 to 1.0).
        """
        if role.detector is not None:
            # Use detector's confidence scoring
            try:
                return role.detector.get_data_type_confidence(None, (column,))
            except Exception:
                pass

        # Fall back to keyword matching via name_hints
        if role.name_hints:
            col_lower = column.lower()
            for hint in role.name_hints:
                if hint.lower() in col_lower:
                    return 0.8
        else:
            # Try matching role.key against column name
            if role.key.lower() in column.lower():
                return 0.7

        return 0.0
