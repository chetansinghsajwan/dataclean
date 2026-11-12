"""Tests for the shared count-only aggregation detector."""

from dataclean.engine.dataframe import Aggregators, count_output_names


def test_lone_count_aggregator() -> None:
    """A single count aggregator means we only need row counts, and the output column
    is simply called count.
    """
    assert count_output_names(Aggregators.count) == ("count",)


def test_iterable_of_counts() -> None:
    """Listing count twice still gives one count column. Two identical counts would
    only repeat each other.
    """
    assert count_output_names([Aggregators.count, Aggregators.count]) == ("count",)


def test_mapping_of_counts_uses_given_names() -> None:
    """When the user supplies a dict, their keys name the output columns, n and total
    here.
    """
    mapping = {"n": Aggregators.count, "total": Aggregators.count}
    assert count_output_names(mapping) == ("n", "total")


def test_mixed_aggregators_are_not_count_only() -> None:
    """If count is mixed with another aggregator such as sum, the count-only shortcut
    is off the table. Returning None tells the caller to take the full path.
    """
    assert count_output_names({"n": Aggregators.count, "s": sum}) is None
    assert count_output_names([Aggregators.count, sum]) is None


def test_other_callable_is_not_count_only() -> None:
    """A plain callable that is not count, like sum, is not a count-only request, so
    the answer is None.
    """
    assert count_output_names(sum) is None


def test_empty_inputs_are_not_count_only() -> None:
    """With nothing to aggregate there is no count to take. We return None and skip the
    shortcut.
    """
    assert count_output_names({}) is None
    assert count_output_names([]) is None
