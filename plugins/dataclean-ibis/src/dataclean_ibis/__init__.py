"""Plugin entry point that registers the Ibis catalog and dataframe backends."""

from dataclean import PluginInfo
from dataclean_ibis.catalog import IbisCatalog
from dataclean_ibis.dataframe import IbisDataFrame

# What dataclean's plugin loader reads to find the Ibis pieces.
info = PluginInfo(
    name="dataclean-ibis",
    catalog_types={
        IbisCatalog,
    },
    dataframe_types={
        IbisDataFrame,
    },
)
