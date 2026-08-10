from dataclean.plugins.info import PluginInfo
from dataclean_pandas.dataframe import PandasDataFrame

info = PluginInfo(
    name="dataclean-pandas",
    dataframe_types={
        PandasDataFrame,
    },
)
