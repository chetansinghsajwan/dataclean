"""Dependency resolver for building execution waves."""

import logging
from collections import defaultdict, deque
from collections.abc import Mapping, Sequence

from dataclean.pipeline.assignments import ColumnAssignment, GroupAssignment
from dataclean.pipeline.entity_extractor import EntityExtractor
from dataclean.pipeline.exceptions import (
    AmbiguousRoleError,
    CycleDetectedError,
    MissingRequiredRoleError,
)

logger = logging.getLogger(__name__)


class DependencyResolver:
    """Resolves dependencies and produces topologically sorted execution waves."""

    def __init__(self, entity_extractor: EntityExtractor) -> None:
        """Initialize with entity extractor."""
        self.entity_extractor = entity_extractor

    def resolve(
        self,
        column_assignments: Sequence[ColumnAssignment],
        group_assignments: Sequence[GroupAssignment],
        context_overrides: Mapping[str, Mapping[str, str]] | None = None,
    ) -> tuple[tuple[ColumnAssignment | GroupAssignment, ...], ...]:
        """
        Build dependency graph and produce topologically sorted execution waves.

        Args:
            column_assignments: Base cleaner assignments to columns.
            group_assignments: Group cleaner assignments.
            context_overrides: User-supplied context overrides.

        Returns:
            Tuple of waves, each wave is a tuple of assignments.

        Raises:
            MissingRequiredRoleError: If required context role cannot be matched.
            AmbiguousRoleError: If role has multiple equally valid producers.
            CycleDetectedError: If dependency cycle is detected.
        """
        context_overrides = context_overrides or {}

        # Build role-to-producers map
        role_producers: dict[str, list[ColumnAssignment | GroupAssignment]] = (
            defaultdict(list)
        )

        # Collect provided roles from cleaners
        for assignment in column_assignments:
            roles = assignment.cleaner.provided_roles()
            for role in roles:
                role_producers[role].append(assignment)

        for assignment in group_assignments:
            roles = assignment.cleaner.provided_roles()
            for role in roles:
                role_producers[role].append(assignment)

        # Resolve context dependencies and build dependency graph
        dependencies: dict[id, set[id]] = defaultdict(set)

        for assignment in column_assignments:
            context_reqs = assignment.cleaner.context_requests()
            for ctx_req in context_reqs:
                role = ctx_req.role
                producers = self._resolve_context_role(
                    role,
                    assignment.column,
                    role_producers,
                    context_overrides,
                    ctx_req.required,
                )

                # Add dependency edges from this assignment to producers
                for producer in producers:
                    dependencies[id(assignment)].add(id(producer))

        for assignment in group_assignments:
            context_reqs = assignment.cleaner.context_requests()
            for ctx_req in context_reqs:
                role = ctx_req.role
                producers = self._resolve_context_role(
                    role,
                    None,
                    role_producers,
                    context_overrides,
                    ctx_req.required,
                )

                # Add dependency edges
                for producer in producers:
                    dependencies[id(assignment)].add(id(producer))

        # Combine all assignments for topological sort
        all_assignments: dict[id, ColumnAssignment | GroupAssignment] = {}
        for a in column_assignments:
            all_assignments[id(a)] = a
        for a in group_assignments:
            all_assignments[id(a)] = a

        # Topological sort with cycle detection
        waves = self._topological_sort_to_waves(all_assignments, dependencies)

        return waves

    def _resolve_context_role(
        self,
        role: str,
        consumer_column: str | None,
        role_producers: dict[str, list],
        context_overrides: Mapping[str, Mapping[str, str]],
        required: bool,
    ) -> list:
        """
        Resolve a context role to producer(s).

        Checks context_overrides first, then picks producer with highest
        entity-token overlap.

        Args:
            role: The semantic role needed.
            consumer_column: Column requesting the role (for entity matching).
            role_producers: Mapping of role -> producer assignments.
            context_overrides: User overrides.
            required: Whether the role is required.

        Returns:
            List of producer assignments.

        Raises:
            MissingRequiredRoleError or AmbiguousRoleError if needed.
        """
        # Check user-supplied overrides first
        if consumer_column and consumer_column in context_overrides:
            overrides = context_overrides[consumer_column]
            if role in overrides:
                # User specified which producer to use for this role
                override_col = overrides[role]
                # Find the producer for this column
                for producer in role_producers.get(role, []):
                    if (
                        isinstance(producer, ColumnAssignment)
                        and producer.column == override_col
                    ):
                        return [producer]
                    elif isinstance(producer, GroupAssignment):
                        # Check if this group's output includes the column
                        for output_col in producer.role_columns.values():
                            if output_col == override_col:
                                return [producer]

        producers = role_producers.get(role, [])

        if not producers:
            if required:
                raise MissingRequiredRoleError(
                    f"Required context role '{role}' has no producer"
                )
            return []

        if len(producers) == 1:
            return producers

        # Multiple producers: disambiguate via entity-token overlap
        if consumer_column:
            consumer_entities = self.entity_extractor.extract(consumer_column, role)
            scores: list[tuple[float, int, object]] = []

            for i, producer in enumerate(producers):
                producer_col = (
                    producer.column if isinstance(producer, ColumnAssignment) else None
                )
                if producer_col:
                    producer_entities = self.entity_extractor.extract(
                        producer_col, role
                    )
                    overlap = self.entity_extractor.entity_overlap(
                        consumer_entities, producer_entities
                    )
                    scores.append((overlap, i, producer))
                else:
                    scores.append((0.0, i, producer))

            scores.sort(reverse=True, key=lambda x: x[0])
            best_score = scores[0][0]

            # Check for ties
            tied_producers = [p for s, _, p in scores if s == best_score]
            if len(tied_producers) > 1:
                if required:
                    raise AmbiguousRoleError(
                        f"Multiple equally valid producers for role '{role}'"
                    )
                # Optional: return empty if ambiguous
                return []

            return [scores[0][2]]

        # No consumer column to match: return all producers if ambiguous
        if len(producers) > 1 and required:
            raise AmbiguousRoleError(
                f"Multiple producers for required role '{role}' and no consumer context"
            )

        return producers

    def _topological_sort_to_waves(
        self,
        assignments: dict[id, ColumnAssignment | GroupAssignment],
        dependencies: dict[id, set[id]],
    ) -> tuple[tuple[ColumnAssignment | GroupAssignment, ...], ...]:
        """
        Perform topological sort with cycle detection.

        Produces waves where each wave contains assignments with no dependencies
        on later assignments.

        Args:
            assignments: Mapping of id -> assignment.
            dependencies: Mapping of id -> set of dependency ids.

        Returns:
            Tuple of waves.

        Raises:
            CycleDetectedError: If cycle is detected.
        """
        in_degree = defaultdict(int)
        adj_list: dict[id, list[id]] = defaultdict(list)

        # Initialize in-degrees
        for aid in assignments:
            if aid not in in_degree:
                in_degree[aid] = 0

        # Build adjacency list (reverse of dependencies)
        for depender, dependees in dependencies.items():
            for dependee in dependees:
                adj_list[dependee].append(depender)
                in_degree[depender] += 1

        # Kahn's algorithm for topological sort
        queue = deque(aid for aid in assignments if in_degree[aid] == 0)
        waves: list[list[ColumnAssignment | GroupAssignment]] = []

        while queue:
            # Current wave contains all nodes with no remaining dependencies
            wave = []
            wave_size = len(queue)

            for _ in range(wave_size):
                aid = queue.popleft()
                wave.append(assignments[aid])

                # Process dependents
                for dependent in adj_list[aid]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

            if wave:
                waves.append(wave)

        # Check for cycles
        if sum(len(w) for w in waves) < len(assignments):
            raise CycleDetectedError("Cycle detected in cleaner dependency graph")

        return tuple(tuple(w) for w in waves)
