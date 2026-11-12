"""Plugin entry point that registers the pandas catalog and dataframe backends."""

from dataclean import PluginInfo
from dataclean_pandas.catalog import PandasCatalog
from dataclean_pandas.dataframe import PandasDataFrame

# What dataclean's plugin loader reads to find the pandas pieces.
info = PluginInfo(
    name="dataclean-pandas",
    catalog_types={
        PandasCatalog,
    },
    dataframe_types={
        PandasDataFrame,
    },
)
