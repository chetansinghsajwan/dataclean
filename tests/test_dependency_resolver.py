"""Tests for context-role resolution and wave ordering in DependencyResolver."""

import pytest

from dataclean import Cleaner, ColRenamer
from dataclean.pipeline import (
    AmbiguousRoleError,
    Assignment,
    CycleDetectedError,
    DependencyResolutionError,
    EntityExtractor,
    MissingRequiredRoleError,
)
from dataclean.pipeline.dependency_resolver import DependencyResolver


def _outputs(role: str) -> Cleaner.OutputSchema:
    return Cleaner.OutputSchema(cols=(Cleaner.OutputSchema.Column(roles=(role,)),))


class ProducesX(Cleaner):
    def _outputs(self) -> Cleaner.OutputSchema:
        return _outputs("x")

    def clean_row(self, value: str | None) -> str | None:
        return value


class ConsumesX(Cleaner):
    def clean_row(self, value: str | None, x: str | None) -> str | None:
        return value


class ConsumesXOptional(Cleaner):
    def clean_row(self, value: str | None, x: str | None = None) -> str | None:
        return value


class ProducesAConsumesB(Cleaner):
    def _outputs(self) -> Cleaner.OutputSchema:
        return _outputs("a")

    def clean_row(self, value: str | None, b: str | None) -> str | None:
        return value


class ProducesBConsumesA(Cleaner):
    def _outputs(self) -> Cleaner.OutputSchema:
        return _outputs("b")

    def clean_row(self, value: str | None, a: str | None) -> str | None:
        return value


@pytest.fixture
def resolver() -> DependencyResolver:
    return DependencyResolver(
        entity_extractor=EntityExtractor(words_fn=ColRenamer()._get_words)
    )


def _assign(cleaner: Cleaner, column: str) -> Assignment:
    return Assignment(cleaner, {"value": column}, 1.0)


def test_error_types_share_a_catchable_base() -> None:
    """There are several ways dependency resolution can fail. They all share one parent
    error, so a caller can catch them in one go."""
    for error in (MissingRequiredRoleError, AmbiguousRoleError, CycleDetectedError):
        assert issubclass(error, DependencyResolutionError)


def test_no_assignments_yields_no_waves(resolver: DependencyResolver) -> None:
    """If there is nothing to run, we get back nothing at all. An empty input is not an
    error."""
    assert resolver.resolve(()) == ()


def test_independent_assignments_share_one_wave(resolver: DependencyResolver) -> None:
    """Two cleaners that don't depend on each other can run side by side. They end up
    in the same wave."""
    waves = resolver.resolve((_assign(ProducesX(), "a"), _assign(ProducesX(), "b")))
    assert len(waves) == 1
    assert len(waves[0]) == 2


def test_single_producer_runs_before_consumer(resolver: DependencyResolver) -> None:
    """One cleaner produces a value that another needs, and we list them in the wrong
    order on purpose. The producer must still run first, in an earlier wave, and its
    column is passed on to the consumer."""
    producer, consumer = ProducesX(), ConsumesX()
    waves = resolver.resolve((_assign(consumer, "c"), _assign(producer, "p")))

    assert [[a.cleaner for a in wave] for wave in waves] == [[producer], [consumer]]
    assert waves[1][0].context_columns == {"x": "p"}


def test_missing_required_role_raises(resolver: DependencyResolver) -> None:
    """A cleaner needs an input that no other cleaner provides. It could never run
    correctly, so we raise an error that names the missing role."""
    with pytest.raises(MissingRequiredRoleError, match="'x'"):
        resolver.resolve((_assign(ConsumesX(), "c"),))


def test_missing_optional_role_is_skipped(resolver: DependencyResolver) -> None:
    """If the missing input is optional, nothing is wrong. The cleaner just runs
    without it."""
    waves = resolver.resolve((_assign(ConsumesXOptional(), "c"),))
    assert len(waves) == 1
    assert waves[0][0].context_columns == {}


def test_ambiguous_producers_without_namespace_signal_raise(
    resolver: DependencyResolver,
) -> None:
    """Two columns could both supply what the consumer needs, and nothing in the names
    hints which one is meant. Picking one at random could mix up someone's data, so
    we stop and ask."""
    assignments = (
        _assign(ProducesX(), "alpha"),
        _assign(ProducesX(), "beta"),
        _assign(ConsumesX(), "c"),
    )
    with pytest.raises(AmbiguousRoleError, match="namespace"):
        resolver.resolve(assignments)


def test_optional_role_with_ambiguous_producers_is_skipped(
    resolver: DependencyResolver,
) -> None:
    """The same two-producer confusion is harmless when the input is optional. We leave
    it unfilled instead of failing."""
    assignments = (
        _assign(ProducesX(), "alpha"),
        _assign(ProducesX(), "beta"),
        _assign(ConsumesXOptional(), "c"),
    )
    waves = resolver.resolve(assignments)
    consumer = next(a for wave in waves for a in wave if a.role_columns["value"] == "c")
    assert consumer.context_columns == {}


def test_entity_overlap_disambiguates_producers(resolver: DependencyResolver) -> None:
    """Column names carry hints. A consumer called manager_val clearly belongs with
    manager_x rather than client_x, so the shared word settles which producer to
    use."""
    assignments = (
        _assign(ProducesX(), "client_x"),
        _assign(ProducesX(), "manager_x"),
        _assign(ConsumesX(), "manager_val"),
    )
    waves = resolver.resolve(assignments)
    consumer = waves[-1][0]
    assert consumer.context_columns == {"x": "manager_x"}


def test_entity_tie_raises(resolver: DependencyResolver) -> None:
    """Here the consumer's name, val, gives no hint toward client or manager. With no
    clear winner we raise, instead of guessing."""
    assignments = (
        _assign(ProducesX(), "client_x"),
        _assign(ProducesX(), "manager_x"),
        _assign(ConsumesX(), "val"),
    )
    with pytest.raises(AmbiguousRoleError, match="disambiguate"):
        resolver.resolve(assignments)


def test_context_override_picks_producer(resolver: DependencyResolver) -> None:
    """When the choice really is ambiguous, the user can settle it by naming the column
    to use. That choice is then followed."""
    assignments = (
        _assign(ProducesX(), "alpha"),
        _assign(ProducesX(), "beta"),
        _assign(ConsumesX(), "c"),
    )
    waves = resolver.resolve(assignments, {"c": {"x": "beta"}})
    assert waves[-1][0].context_columns == {"x": "beta"}


def test_context_override_to_non_producer_raises(resolver: DependencyResolver) -> None:
    """If the user points at a column that doesn't actually produce the needed value,
    using it would silently give wrong data. We raise an error instead."""
    assignments = (_assign(ProducesX(), "alpha"), _assign(ConsumesX(), "c"))
    with pytest.raises(MissingRequiredRoleError, match="override"):
        resolver.resolve(assignments, {"c": {"x": "nope"}})


def test_cycle_raises(resolver: DependencyResolver) -> None:
    """Two cleaners that each need the other's output can never be put in order. We
    detect this loop and raise an error."""
    assignments = (
        _assign(ProducesAConsumesB(), "p"),
        _assign(ProducesBConsumesA(), "q"),
    )
    with pytest.raises(CycleDetectedError):
        resolver.resolve(assignments)


class ProducesAndConsumesX(Cleaner):
    def _outputs(self) -> Cleaner.OutputSchema:
        return _outputs("x")

    def clean_row(self, value: str | None, x: str | None = None) -> str | None:
        return value


def test_cleaner_is_not_its_own_producer(resolver: DependencyResolver) -> None:
    """A cleaner that both produces and optionally consumes the same role shouldn't
    feed itself. That would be a made-up dependency on its own output, so it runs
    alone with nothing supplied."""
    waves = resolver.resolve((_assign(ProducesAndConsumesX(), "c"),))

    assert len(waves) == 1
    assert waves[0][0].context_columns == {}


def test_other_producer_still_satisfies_a_self_producing_consumer(
    resolver: DependencyResolver,
) -> None:
    """That same cleaner can still get the value from a different cleaner. The other
    one runs first and its column is passed along."""
    other = ProducesX()
    waves = resolver.resolve(
        (_assign(ProducesAndConsumesX(), "c"), _assign(other, "p"))
    )

    assert [[a.cleaner for a in wave][0] is other for wave in waves[:1]] == [True]
    assert waves[1][0].context_columns == {"x": "p"}
