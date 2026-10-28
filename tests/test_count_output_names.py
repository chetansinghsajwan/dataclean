"""Tests for the shared count-only aggregation detector."""

from dataclean.engine.dataframe import Aggregators, count_output_names


def test_lone_count_aggregator() -> None:
    assert count_output_names(Aggregators.count) == ("count",)


def test_iterable_of_counts() -> None:
    assert count_output_names([Aggregators.count, Aggregators.count]) == ("count",)


def test_mapping_of_counts_uses_given_names() -> None:
    mapping = {"n": Aggregators.count, "total": Aggregators.count}
    assert count_output_names(mapping) == ("n", "total")


def test_mixed_aggregators_are_not_count_only() -> None:
    assert count_output_names({"n": Aggregators.count, "s": sum}) is None
    assert count_output_names([Aggregators.count, sum]) is None


def test_other_callable_is_not_count_only() -> None:
    assert count_output_names(sum) is None


def test_empty_inputs_are_not_count_only() -> None:
    assert count_output_names({}) is None
    assert count_output_names([]) is None
