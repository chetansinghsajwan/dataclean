"""Build dependency-safe execution waves for unified cleaner assignments."""

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import replace

from dataclean.cleaners.cleaner import PRIMARY
from dataclean.pipeline.assignments import Assignment
from dataclean.pipeline.entity_extractor import EntityExtractor
from dataclean.pipeline.exceptions import (
    AmbiguousRoleError,
    CycleDetectedError,
    MissingRequiredRoleError,
)


class DependencyResolver:
    """Resolve context providers and topologically sort assignments into waves."""

    def __init__(self, entity_extractor: EntityExtractor) -> None:
        self._entity_extractor = entity_extractor

    def resolve(
        self,
        assignments: Sequence[Assignment],
        context_overrides: Mapping[str, Mapping[str, str]] | None = None,
    ) -> tuple[tuple[Assignment, ...], ...]:
        """Resolve context roles and return execution waves."""
        overrides = context_overrides or {}
        assignment_list = tuple(assignments)
        producers: dict[str, list[int]] = defaultdict(list)
        for index, assignment in enumerate(assignment_list):
            for role in assignment.cleaner.provided_roles():
                producers[role].append(index)

        dependencies: dict[int, set[int]] = defaultdict(set)
        resolved_context: dict[int, dict[str, str]] = defaultdict(dict)
        for index, assignment in enumerate(assignment_list):
            consumer_column = assignment.role_columns.get(PRIMARY)
            for role in assignment.cleaner.resolved_input_roles:
                if role.key == PRIMARY or role.key in assignment.role_columns:
                    continue
                producer_index = self._resolve_producer(
                    role.key,
                    role.required,
                    consumer_column,
                    producers,
                    assignment_list,
                    overrides,
                )
                if producer_index is None:
                    continue
                dependencies[index].add(producer_index)
                resolved_context[index][role.key] = self._output_column(
                    assignment_list[producer_index], role.key
                )

        resolved_assignments = tuple(
            replace(assignment, context_columns=resolved_context[index])
            for index, assignment in enumerate(assignment_list)
        )
        return self._topological_waves(resolved_assignments, dependencies)

    def _resolve_producer(
        self,
        role: str,
        required: bool,
        consumer_column: str | None,
        producers: Mapping[str, list[int]],
        assignments: Sequence[Assignment],
        overrides: Mapping[str, Mapping[str, str]],
    ) -> int | None:
        candidates = producers.get(role, [])
        if consumer_column is not None and role in overrides.get(consumer_column, {}):
            requested_column = overrides[consumer_column][role]
            for candidate in candidates:
                if requested_column in assignments[candidate].role_columns.values():
                    return candidate
            raise MissingRequiredRoleError(
                f"Context override for role '{role}' references no matching producer"
            )
        if not candidates:
            if required:
                raise MissingRequiredRoleError(
                    f"Required context role '{role}' has no producer"
                )
            return None
        if len(candidates) == 1:
            return candidates[0]
        if consumer_column is None:
            if required:
                raise AmbiguousRoleError(
                    f"Multiple producers for required role '{role}'"
                )
            return None

        role_token = role.lower()
        candidate_columns = [
            self._producer_identity(assignments[candidate]) for candidate in candidates
        ]
        if not all(role_token in column.lower() for column in candidate_columns):
            if required:
                raise AmbiguousRoleError(
                    f"Role '{role}' has producers without namespace signals"
                )
            return None
        consumer_entities = self._entity_extractor.extract(consumer_column, role)
        scores = [
            self._entity_extractor.entity_overlap(
                consumer_entities, self._entity_extractor.extract(column, role)
            )
            for column in candidate_columns
        ]
        best_score = max(scores)
        if best_score == 0.0 or scores.count(best_score) != 1:
            if required:
                raise AmbiguousRoleError(
                    f"Unable to disambiguate required role '{role}'"
                )
            return None
        return candidates[scores.index(best_score)]

    def _producer_identity(self, assignment: Assignment) -> str:
        return assignment.role_columns.get(
            PRIMARY, next(iter(assignment.role_columns.values()))
        )

    def _output_column(self, assignment: Assignment, role: str) -> str:
        schema = assignment.cleaner.output_schema()
        if isinstance(schema, tuple):
            for output_column, _ in schema:
                if output_column == role:
                    return output_column
        return assignment.role_columns.get(
            PRIMARY, next(iter(assignment.role_columns.values()))
        )

    def _topological_waves(
        self, assignments: Sequence[Assignment], dependencies: Mapping[int, set[int]]
    ) -> tuple[tuple[Assignment, ...], ...]:
        in_degree = [0] * len(assignments)
        dependents: dict[int, list[int]] = defaultdict(list)
        for assignment_index, producers in dependencies.items():
            for producer in producers:
                in_degree[assignment_index] += 1
                dependents[producer].append(assignment_index)
        queue = deque(index for index, degree in enumerate(in_degree) if degree == 0)
        waves: list[tuple[Assignment, ...]] = []
        visited = 0
        while queue:
            current_indices = tuple(queue)
            queue.clear()
            waves.append(tuple(assignments[index] for index in current_indices))
            visited += len(current_indices)
            for index in current_indices:
                for dependent in dependents[index]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        if visited != len(assignments):
            raise CycleDetectedError("Cycle detected in cleaner dependency graph")
        return tuple(waves)
