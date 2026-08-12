from dataclean.plugins.info import PluginInfo
from dataclean_databricks.catalog import UnityCatalog
from dataclean_databricks.dataframe import PysparkDataFrame

info = PluginInfo(
    name="dataclean-databricks",
    catalog_types={
        UnityCatalog,
    },
    dataframe_types={
        PysparkDataFrame,
    },
)
