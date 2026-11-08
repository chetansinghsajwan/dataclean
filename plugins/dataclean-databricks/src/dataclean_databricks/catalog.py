import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import ClassVar, Self, override

from databricks.connect import DatabricksEnv, DatabricksSession

from dataclean import Catalog, DataFrame, checked
from dataclean.utils.patterns import (
    REGEX_PREFIX,
    compile_regex,
    has_glob,
    is_regex,
)
from dataclean_databricks.dataframe import PysparkDataFrame
from dataclean_databricks.types import SparkSession

# Set to a true value to let a new session upload local packages (including
# dataclean) to the workspace so the UDF workers can import them. Off by
# default, because the upload writes to the workspace.
UPLOAD_LOCAL_ENV = "DATACLEAN_DATABRICKS_UPLOAD_LOCAL"


def upload_local_enabled() -> bool:
    """Whether ``UPLOAD_LOCAL_ENV`` asks sessions to upload local packages."""
    return os.environ.get(UPLOAD_LOCAL_ENV, "").strip().lower() in {"1", "true", "yes"}


def new_session() -> SparkSession:
    """Open a Databricks Connect session from the environment's credentials.

    Local packages are uploaded to the workspace only when
    ``UPLOAD_LOCAL_ENV`` is set. Otherwise ``dataclean`` must already be
    installed on the cluster for cleaners to run in UDFs.
    """
    builder = DatabricksSession.builder
    if upload_local_enabled():
        builder = builder.withEnvironment(
            DatabricksEnv().withAutoDependencies(upload_local=True)
        )
    return builder.getOrCreate()


@checked
@dataclass
class UnityCatalog(Catalog):
    spark: SparkSession
    write_options: dict[str, str] = field(default_factory=dict)

    schemes: ClassVar[tuple[str, ...]] = ("databricks",)

    @classmethod
    @override
    def instantiate(cls) -> Self | None:
        return cls(spark=new_session())

    @override
    def expand_paths(self, paths: Iterable[str]) -> set[str]:
        return self._expand_paths(paths=paths, spark=self.spark)

    @override
    def read_df(self, path: str) -> PysparkDataFrame:
        sdf = self.spark.read.table(path)
        return PysparkDataFrame(df=sdf)

    @override
    def write_df(self, df: DataFrame, path: str) -> None:
        assert isinstance(df, PysparkDataFrame)

        df.df.write.options(**self.write_options).saveAsTable(path)

    @staticmethod
    def _expand_paths(paths: Iterable[str], spark: SparkSession) -> set[str]:
        """Expand table path patterns into fully-qualified table names.

        A pattern is ``catalog``, ``catalog.schema`` or ``catalog.schema.table``
        (missing parts count as ``*``), where each part may use ``*`` and ``?``
        wildcards, or a regex written ``re:<regex>`` that must match the whole
        ``catalog.schema.table`` name. A pattern without wildcards is returned
        as it is, without asking the metastore. All other patterns are looked up
        in one query on ``information_schema``, and every value reaches it as a
        bound parameter, never as SQL text.

        Raises:
            ValueError: If a regex pattern is not a valid regex.
        """
        results: set[str] = set()
        conditions: list[str] = []
        params: dict[str, str] = {}

        for index, path in enumerate(paths):
            path = path.strip().replace("`", "")

            if is_regex(path):
                compile_regex(path)  # fail early on a bad regex
                params[f"r{index}"] = f"^(?:{path.removeprefix(REGEX_PREFIX)})$"
                conditions.append(
                    "(concat_ws('.', table_catalog, table_schema, table_name)"
                    f" RLIKE :r{index})"
                )
                continue

            parts = [part for part in path.split(".") if part]
            parts += ["*"] * (3 - len(parts))
            catalog_part, schema_part, table_part = parts[:3]

            if not any(
                has_glob(part) for part in (catalog_part, schema_part, table_part)
            ):
                results.add(f"{catalog_part}.{schema_part}.{table_part}")
                continue

            clauses = []
            for column, key, part in (
                ("table_catalog", f"c{index}", catalog_part),
                ("table_schema", f"s{index}", schema_part),
                ("table_name", f"t{index}", table_part),
            ):
                if has_glob(part):
                    params[key] = UnityCatalog._glob_to_like(part)
                    clauses.append(f"{column} LIKE :{key}")
                else:
                    params[key] = part
                    clauses.append(f"{column} = :{key}")
            conditions.append(f"({' AND '.join(clauses)})")

        if conditions:
            query = f"""
                SELECT table_catalog, table_schema, table_name
                FROM system.information_schema.tables
                WHERE table_schema != 'information_schema'
                AND table_type IN ('MANAGED', 'EXTERNAL')
                AND ({" OR ".join(conditions)})
            """
            for row in spark.sql(query, args=params).collect():
                results.add(
                    f"{row['table_catalog']}.{row['table_schema']}.{row['table_name']}"
                )

        return results

    @staticmethod
    def _glob_to_like(part: str) -> str:
        """Turn a glob into a SQL ``LIKE`` pattern, matching ``%``, ``_`` and ``\\`` literally."""
        like = []
        for char in part:
            if char == "*":
                like.append("%")
            elif char == "?":
                like.append("_")
            elif char in "%_\\":
                like.append("\\" + char)
            else:
                like.append(char)
        return "".join(like)
