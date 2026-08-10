from dataclean.plugins.info import PluginInfo
from dataclean_pyspark.dataframe import PySparkDataFrame

info = PluginInfo(
    name="dataclean-pyspark",
    dataframe_types={
        PySparkDataFrame,
    },
)
