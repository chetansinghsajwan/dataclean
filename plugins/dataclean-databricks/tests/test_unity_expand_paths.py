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
        """Holds the rows the fake query result will return."""
        self._rows = rows

    def collect(self) -> list[dict[str, str]]:
        """Returns the stored rows like a Spark result would."""
        return self._rows


class FakeSpark(SparkSession):
    def __init__(self, rows: list[dict[str, str]] | None = None) -> None:
        """Starts with canned rows and an empty call log to inspect what was queried."""
        self.rows = rows or []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def sql(self, query: str, args: Any = None, **kwargs: Any) -> _Result:  # ty: ignore[invalid-method-override]
        """Records the query and its bound parameters instead of running anything."""
        self.calls.append((query, dict(args or {})))
        return _Result(self.rows)


def _row(catalog: str, schema: str, table: str) -> dict[str, str]:
    """Builds one information_schema row, the shape the metastore query returns."""
    return {"table_catalog": catalog, "table_schema": schema, "table_name": table}


def test_literal_table_names_do_not_query_the_metastore() -> None:
    """Table names with no wildcards are returned just as given. We make no call to the
    metastore, since there is nothing to look up.
    """
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
    """A glob turns into LIKE conditions with the values passed as bound parameters.
    Nothing the user typed is ever pasted into the SQL text.
    """
    spark = FakeSpark()

    UnityCatalog._expand_paths([pattern], spark)

    query, args = spark.calls[0]
    assert args == params
    assert clauses in query
    assert "prod" not in query  # values are never part of the SQL text


def test_underscore_and_percent_in_a_name_are_matched_literally() -> None:
    """In LIKE an underscore and a percent sign are wildcards, so real ones in a table
    name, like cust_ or 100%, get escaped. Otherwise they would match far too much.
    """
    spark = FakeSpark()

    UnityCatalog._expand_paths(["prod.raw.cust_*", "prod.raw.100%*"], spark)

    _, args = spark.calls[0]
    assert args["t0"] == "cust\\_%"
    assert args["t1"] == "100\\%%"


def test_a_quote_in_a_pattern_stays_in_the_parameter() -> None:
    """Someone types a pattern with a quote and an OR clause in it. It stays inside the
    bound parameter and never reaches the query text, which is what blocks SQL
    injection.
    """
    spark = FakeSpark()

    UnityCatalog._expand_paths(["prod.raw.x' OR '1'='1*"], spark)

    query, args = spark.calls[0]
    assert args["t0"] == "x' OR '1'='1%"
    assert "OR '1'='1" not in query


def test_several_patterns_run_as_one_query() -> None:
    """Three patterns, one of them a plain name, are answered with a single query. One
    trip to the workspace instead of many keeps things quick.
    """
    spark = FakeSpark([_row("prod", "raw", "a"), _row("dev", "raw", "b")])

    result = UnityCatalog._expand_paths(["prod.raw.*", "dev.*.b", "x.y.z"], spark)

    assert len(spark.calls) == 1
    assert result == {"prod.raw.a", "dev.raw.b", "x.y.z"}


def test_regex_matches_the_whole_qualified_name_with_rlike() -> None:
    """A re: pattern gets anchored so it must match the whole catalog.schema.table
    name, and is compared with RLIKE. Without that, a partial hit would pull in
    tables nobody asked for.
    """
    spark = FakeSpark([_row("prod", "raw", "cust_1")])

    result = UnityCatalog._expand_paths([r"re:prod\.raw\.cust_\d+"], spark)

    query, args = spark.calls[0]
    assert "RLIKE :r0" in query
    assert "concat_ws('.', table_catalog, table_schema, table_name)" in query
    assert args == {"r0": r"^(?:prod\.raw\.cust_\d+)$"}
    assert result == {"prod.raw.cust_1"}


def test_invalid_regex_raises_before_querying() -> None:
    """A broken regex, such as an unclosed bracket, should raise an error straight
    away. No query should be sent to the workspace first.
    """
    spark = FakeSpark()

    with pytest.raises(ValueError, match="Invalid regex"):
        UnityCatalog._expand_paths(["re:(unclosed"], spark)

    assert spark.calls == []
