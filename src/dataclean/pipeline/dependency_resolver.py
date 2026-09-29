"""Build dependency-safe execution waves for unified cleaner assignments."""

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from dataclean.cleaners import PRIMARY
from dataclean.types import checked

from .assignments import Assignment
from .entity_extractor import EntityExtractor
from .exceptions import (
    AmbiguousRoleError,
    CycleDetectedError,
    MissingRequiredRoleError,
)


@checked
@dataclass(kw_only=True)
class DependencyResolver:
    """Resolve context providers and topologically sort assignments into waves.

    A cleaner's non-primary input roles are "context roles": values it needs
    that are produced as outputs of other cleaners (rather than read directly
    from a raw column). This resolver matches each consuming assignment's
    context roles to a producing assignment's declared output roles, then
    orders all assignments into dependency-safe execution waves so that every
    producer runs in an earlier (or the same, if independent) wave than its
    consumers.

    Attributes:
        entity_extractor: Used to disambiguate between multiple candidate
            producers for the same role by comparing entity tokens in their
            column names (e.g. "client_phone" vs "manager_phone").
    """

    entity_extractor: EntityExtractor

    def resolve(
        self,
        assignments: Sequence[Assignment],
        context_overrides: Mapping[str, Mapping[str, str]] | None = None,
    ) -> tuple[tuple[Assignment, ...], ...]:
        """Resolve context roles and return execution waves.

        For each assignment's non-primary, unfilled input roles, finds the
        assignment that produces that role (via its output schema's `roles`)
        and records the dependency. The resulting assignments (with
        `context_columns` populated) are then topologically sorted into
        waves of assignments that can run independently of one another.

        Args:
            assignments: The assignments to resolve dependencies for and
                order into waves.
            context_overrides: Optional mapping of consumer column name to a
                mapping of role name to the specific producer column name
                that should supply it, used to disambiguate when automatic
                matching would otherwise be ambiguous. Defaults to None.

        Returns:
            A tuple of waves, where each wave is a tuple of `Assignment`
            objects (with `context_columns` resolved) that have no
            dependencies on one another.

        Raises:
            MissingRequiredRoleError: If a required context role has no
                producer, or a context override names a column that no
                producer of that role actually writes.
            AmbiguousRoleError: If a required context role has multiple
                candidate producers that cannot be disambiguated by namespace
                signal or entity-token overlap.
            CycleDetectedError: If the resolved dependencies form a cycle,
                making a valid execution order impossible.
        """

        overrides = context_overrides or {}
        assignment_list = tuple(assignments)
        producers: dict[str, list[int]] = defaultdict(list)
        for index, assignment in enumerate(assignment_list):
            outputs = getattr(assignment.cleaner, "outputs", None)
            cols = outputs.cols if outputs is not None else ()
            for col in cols:
                for role in col.roles:
                    producers[role].append(index)

        dependencies: dict[int, set[int]] = defaultdict(set)
        resolved_context: dict[int, dict[str, str]] = defaultdict(dict)
        for index, assignment in enumerate(assignment_list):
            consumer_column = assignment.role_columns.get(PRIMARY)
            for col in assignment.cleaner.inputs.cols:
                if col.key == PRIMARY or col.key in assignment.role_columns:
                    continue
                producer_index = self._resolve_producer(
                    col.key,
                    col.required,
                    consumer_column,
                    producers,
                    assignment_list,
                    overrides,
                )
                if producer_index is None:
                    continue
                dependencies[index].add(producer_index)
                resolved_context[index][col.key] = self._output_column(
                    assignment_list[producer_index], col.key
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
        """Determine which assignment (if any) produces a given context role.

        Resolution proceeds through several strategies in order: an explicit
        context override for the consumer column, a single unambiguous
        candidate, disambiguation by namespace signal (the role name
        appearing in each candidate's identifying column), and finally
        disambiguation by entity-token overlap between the consumer and
        candidate column names.

        Args:
            role: The context role key to find a producer for.
            required: Whether this role is required by the consuming cleaner.
                Governs whether an unresolved role raises or is skipped.
            consumer_column: The primary input column of the consuming
                assignment, used for override lookups and entity-token
                comparisons. May be None for cleaners without a primary
                column.
            producers: Mapping of role name to the indices of assignments
                (within `assignments`) that declare producing that role.
            assignments: All assignments being resolved, indexed the same way
                as `producers`.
            overrides: Mapping of consumer column name to a mapping of role
                name to the specific producer column name that should supply
                it.

        Returns:
            The index of the producing assignment, or None if the role is
            optional and could not be resolved.

        Raises:
            MissingRequiredRoleError: If `role` is required and has no
                producer, or an override for `role` names a column that no
                candidate producer actually writes.
            AmbiguousRoleError: If `role` is required and has multiple
                producers that cannot be disambiguated by namespace signal or
                entity-token overlap.
        """
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

        consumer_entities = self.entity_extractor.extract(consumer_column, role)
        scores = [
            self.entity_extractor.overlap(
                consumer_entities, self.entity_extractor.extract(column, role)
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
        """Return the column name that identifies a producer assignment.

        Used as the namespace/entity signal for disambiguation: the
        assignment's primary input column if it has one, otherwise its first
        role column.
        """
        return assignment.role_columns.get(
            PRIMARY, next(iter(assignment.role_columns.values()))
        )

    def _output_column(self, assignment: Assignment, role: str) -> str:
        """Determine the output column name a producer will write for a role.

        Prefers the cleaner's explicitly declared output column name for the
        matching output; otherwise falls back to the producer assignment's
        primary (or first) input column, since single-column cleaners
        overwrite their input column in place.

        Args:
            assignment: The producing assignment.
            role: The role name to find the output column for.

        Returns:
            The column name the producer's output for `role` will be written
            to.
        """
        outputs = getattr(assignment.cleaner, "outputs", None)
        cols = outputs.cols if outputs is not None else ()

        for col in cols:
            if role in col.roles:
                # If the cleaner declares an explicit output column name, use it.
                if col.name:
                    return col.name
                # Otherwise fall back to the producer's primary input column
                return assignment.role_columns.get(
                    PRIMARY, next(iter(assignment.role_columns.values()))
                )

        # Default fallback: producer's primary input column
        return assignment.role_columns.get(
            PRIMARY, next(iter(assignment.role_columns.values()))
        )

    def _topological_waves(
        self, assignments: Sequence[Assignment], dependencies: Mapping[int, set[int]]
    ) -> tuple[tuple[Assignment, ...], ...]:
        """Group assignments into dependency-safe waves via Kahn's algorithm.

        Each wave contains every assignment whose dependencies have all been
        satisfied by prior waves (in-degree zero), so assignments within a
        wave are independent of one another and may run in any order.

        Args:
            assignments: The assignments to order, indexed the same way as
                `dependencies`.
            dependencies: Mapping of assignment index to the set of
                assignment indices it depends on (must run after).

        Returns:
            A tuple of waves, each a tuple of `Assignment` objects, ordered so
            that every assignment appears in a later wave than all of its
            dependencies.

        Raises:
            CycleDetectedError: If not every assignment could be visited,
                meaning the dependency graph contains a cycle.
        """

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
