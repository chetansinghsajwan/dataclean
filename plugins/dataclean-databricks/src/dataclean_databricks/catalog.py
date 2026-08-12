import fnmatch
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import ClassVar, Self, override

from databricks.connect import DatabricksSession

from dataclean import Catalog, CatalogPriority, DataFrame, checked
from dataclean_databricks.dataframe import PysparkDataFrame
from dataclean_databricks.types import SparkSession


@checked
@dataclass
class UnityCatalog(Catalog):
    spark: SparkSession
    write_options: dict[str, str] = field(default_factory=dict)

    priority: ClassVar[int] = CatalogPriority.ENV_DEPENDENT

    @classmethod
    @override
    def supports_env(cls) -> bool:

        if os.environ.get("DATABRICKS_RUNTIME_VERSION") is not None:
            return True

        if (
            os.environ.get("DATABRICKS_HOST") is not None
            and os.environ.get("DATABRICKS_TOKEN") is not None
            and os.environ.get("DATABRICKS_CLUSTER_ID") is not None
        ):
            return True

        return False

    @classmethod
    @override
    def instantiate(cls) -> Self | None:
        spark = DatabricksSession.builder.getOrCreate()
        return cls(spark=spark)

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
        """
        Expands a list of database path patterns containing wildcards into a deduplicated
        list of fully-qualified table names.
        """

        results = set()
        query_conditions = []

        for path in paths:
            # Clean and split path components
            clean_path = path.strip().replace("`", "")
            parts = [p for p in clean_path.split(".") if p]

            # Pad missing structural layers with wildcards
            if len(parts) == 1:
                cat_pattern, sch_pattern, tab_pattern = parts[0], "*", "*"
            elif len(parts) == 2:
                cat_pattern, sch_pattern, tab_pattern = parts[0], parts[1], "*"
            else:
                cat_pattern, sch_pattern, tab_pattern = parts[0], parts[1], parts[2]

            # SHORT-CIRCUIT: Direct append if no wildcards exist for this path pattern
            if (
                "*" not in cat_pattern
                and "*" not in sch_pattern
                and "*" not in tab_pattern
            ):
                results.add(f"{cat_pattern}.{sch_pattern}.{tab_pattern}")
                continue

            # Map simple wildcards down to SQL LIKE compliant filters on a per-component basis
            cat_clause = (
                f"table_catalog LIKE '{cat_pattern.replace('*', '%')}'"
                if "*" in cat_pattern
                else f"table_catalog = '{cat_pattern}'"
            )
            sch_clause = (
                f"table_schema LIKE '{sch_pattern.replace('*', '%')}'"
                if "*" in sch_pattern
                else f"table_schema = '{sch_pattern}'"
            )
            tab_clause = (
                f"table_name LIKE '{tab_pattern.replace('*', '%')}'"
                if "*" in tab_pattern
                else f"table_name = '{tab_pattern}'"
            )

            # Combine matching filters to form an isolated search group window
            query_conditions.append(f"({cat_clause} AND {sch_clause} AND {tab_clause})")

        # If any query patterns exist, process them all inside exactly ONE collective metadata query pass
        if query_conditions:
            master_query = f"""
                SELECT table_catalog, table_schema, table_name
                FROM system.information_schema.tables
                WHERE table_schema != 'information_schema'
                AND table_type IN ('MANAGED', 'EXTERNAL')
                AND ({" OR ".join(query_conditions)})
            """

            # Fetch and safely unpack entries into our master collection matrix
            for row in spark.sql(master_query).collect():
                results.add(
                    f"{row['table_catalog']}.{row['table_schema']}.{row['table_name']}"
                )

        return results

    @staticmethod
    def _expand_path_to(src: str, dest: str) -> str:
        """
        Private translation engine that maps a fully qualified source path string
        (guaranteed to be catalog.schema.table) to its corresponding target destination
        based on the platform's asymmetrical sub-flattening layout rules.
        """

        src_parts = src.replace("`", "").split(".")  # [catalog, schema, table]
        dest_parts = [d.replace("`", "") for d in dest.split(".") if d]

        # Rule A: Destination is just a Catalog -> Maintain full underlying hierarchy
        if len(dest_parts) == 1:
            d_catalog = dest_parts[0]
            d_schema = src_parts[1]
            d_table = src_parts[2]

        # Rule B: Destination is Catalog.Schema -> Apply the schema-table flattening/un-nesting rule
        elif len(dest_parts) == 2:
            # Example: prod_raw.hp_live_practice.isol1402 -> dev.raw
            # Resolves to: dev.raw.hp_live_practice_isol1402
            d_catalog = dest_parts[0]
            d_schema = dest_parts[1]
            d_table = f"{src_parts[1]}_{src_parts[2]}"

        # Rule C: Destination is fully-qualified Catalog.Schema.Table Pattern
        elif len(dest_parts) == 3:
            d_catalog = dest_parts[0]
            d_schema = dest_parts[1]
            dest_table_pattern = dest_parts[2]

            # Process standard suffix/prefix token partitions around wildcards
            if "*" in dest_table_pattern:
                prefix, _, suffix = dest_table_pattern.partition("*")
                d_table = f"{prefix}{src_parts[2]}{suffix}"
            else:
                d_table = dest_table_pattern
        else:
            raise Exception(
                f"Invalid destination namespace depth parsing target layout: '{dest}'"
            )

        # Clean out syntax anomalies or legacy dangling markers
        d_table = d_table.replace("*", "")

        return f"{d_catalog}.{d_schema}.{d_table}"

    @staticmethod
    def _expand_path_maps(
        paths: dict[str, str],
        spark: SparkSession,
    ) -> dict[str, str]:
        """
        Orchestrates the batch expansion of a collection of source-to-destination
        path patterns into a single unified tracking map using exactly ONE database query pass.
        """

        if not paths:
            return {}

        # 1. BATCH PRE-FETCH: Resolve ALL source patterns simultaneously in exactly one network round-trip
        all_src_patterns = list(paths.keys())
        all_expanded_sources = UnityCatalog._expand_paths(
            paths=all_src_patterns, spark=spark
        )

        if not all_expanded_sources:
            return {}

        unified_tables_map = {}

        # 2. Map concrete assets back to original patterns entirely inside local worker memory
        for src_table in all_expanded_sources:
            src_parts = src_table.split(".")

            matched_src_pattern = None
            for src_pattern in paths:
                clean_pattern = src_pattern.strip().replace("`", "")
                p_parts = [p for p in clean_pattern.split(".") if p]

                p_cat = p_parts[0]
                p_sch = p_parts[1] if len(p_parts) >= 2 else "*"
                p_tab = p_parts[2] if len(p_parts) == 3 else "*"

                if (
                    fnmatch.fnmatch(src_parts[0], p_cat)
                    and fnmatch.fnmatch(src_parts[1], p_sch)
                    and fnmatch.fnmatch(src_parts[2], p_tab)
                ):
                    matched_src_pattern = src_pattern
                    break

            if not matched_src_pattern:
                continue

            # Route matching components into the isolated, encapsulated private transformer function
            dest_pattern = paths[matched_src_pattern]
            unified_tables_map[src_table] = UnityCatalog._expand_path_to(
                src_table, dest_pattern
            )

        return unified_tables_map
