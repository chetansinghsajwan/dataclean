"""Plugin entry point that registers the Unity Catalog and PySpark backends."""

from dataclean import PluginInfo
from dataclean_databricks.catalog import UnityCatalog
from dataclean_databricks.dataframe import PysparkDataFrame

# What dataclean's plugin loader reads to find the Unity Catalog and PySpark pieces.
info = PluginInfo(
    name="dataclean-databricks",
    catalog_types={
        UnityCatalog,
    },
    dataframe_types={
        PysparkDataFrame,
    },
)
