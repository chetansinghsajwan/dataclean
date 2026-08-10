from dataclean.plugins.info import PluginInfo
from dataclean_pyspark.catalog import PySparkCatalog
from dataclean_pyspark.dataframe import PySparkDataFrame

info = PluginInfo(
    name="dataclean-pyspark",
    catalog_types={
        PySparkCatalog,
    },
    dataframe_types={
        PySparkDataFrame,
    },
)
