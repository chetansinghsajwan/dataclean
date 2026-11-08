"""Path expansion tests for ``UnityCatalog`` with a fake Spark session.

They need no workspace: the fake records each query and its bound
parameters, and answers with canned rows.
"""

from typing import Any

import pytest
from dataclean_databricks.catalog import UnityCatalog
from pyspark.sql import SparkSession


class _Result:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self._rows = rows

    def collect(self) -> list[dict[str, str]]:
        return self._rows


class FakeSpark(SparkSession):
    def __init__(self, rows: list[dict[str, str]] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def sql(self, query: str, args: Any = None, **kwargs: Any) -> _Result:  # ty: ignore[invalid-method-override]
        self.calls.append((query, dict(args or {})))
        return _Result(self.rows)


def _row(catalog: str, schema: str, table: str) -> dict[str, str]:
    return {"table_catalog": catalog, "table_schema": schema, "table_name": table}


def test_literal_table_names_do_not_query_the_metastore() -> None:
    spark = FakeSpark()

    assert UnityCatalog._expand_paths(["prod.raw.customers"], spark) == {
        "prod.raw.customers"
    }
    assert spark.calls == []


@pytest.mark.parametrize(
    "pattern, params, clauses",
    [
        ("prod.raw.*", {"c0": "prod", "s0": "raw", "t0": "%"}, "table_name LIKE :t0"),
        ("prod.raw", {"c0": "prod", "s0": "raw", "t0": "%"}, "table_name LIKE :t0"),
        ("prod", {"c0": "prod", "s0": "%", "t0": "%"}, "table_schema LIKE :s0"),
        (
            "prod.*.clients",
            {"c0": "prod", "s0": "%", "t0": "clients"},
            "table_name = :t0",
        ),
        ("prod.raw.cust_?", {"c0": "prod", "s0": "raw", "t0": "cust\\__"}, "LIKE :t0"),
    ],
)
def test_globs_become_bound_like_parameters(
    pattern: str, params: dict[str, str], clauses: str
) -> None:
    spark = FakeSpark()

    UnityCatalog._expand_paths([pattern], spark)

    query, args = spark.calls[0]
    assert args == params
    assert clauses in query
    assert "prod" not in query  # values are never part of the SQL text


def test_underscore_and_percent_in_a_name_are_matched_literally() -> None:
    spark = FakeSpark()

    UnityCatalog._expand_paths(["prod.raw.cust_*", "prod.raw.100%*"], spark)

    _, args = spark.calls[0]
    assert args["t0"] == "cust\\_%"
    assert args["t1"] == "100\\%%"


def test_a_quote_in_a_pattern_stays_in_the_parameter() -> None:
    spark = FakeSpark()

    UnityCatalog._expand_paths(["prod.raw.x' OR '1'='1*"], spark)

    query, args = spark.calls[0]
    assert args["t0"] == "x' OR '1'='1%"
    assert "OR '1'='1" not in query


def test_several_patterns_run_as_one_query() -> None:
    spark = FakeSpark([_row("prod", "raw", "a"), _row("dev", "raw", "b")])

    result = UnityCatalog._expand_paths(["prod.raw.*", "dev.*.b", "x.y.z"], spark)

    assert len(spark.calls) == 1
    assert result == {"prod.raw.a", "dev.raw.b", "x.y.z"}


def test_regex_matches_the_whole_qualified_name_with_rlike() -> None:
    spark = FakeSpark([_row("prod", "raw", "cust_1")])

    result = UnityCatalog._expand_paths([r"re:prod\.raw\.cust_\d+"], spark)

    query, args = spark.calls[0]
    assert "RLIKE :r0" in query
    assert "concat_ws('.', table_catalog, table_schema, table_name)" in query
    assert args == {"r0": r"^(?:prod\.raw\.cust_\d+)$"}
    assert result == {"prod.raw.cust_1"}


def test_invalid_regex_raises_before_querying() -> None:
    spark = FakeSpark()

    with pytest.raises(ValueError, match="Invalid regex"):
        UnityCatalog._expand_paths(["re:(unclosed"], spark)

    assert spark.calls == []
