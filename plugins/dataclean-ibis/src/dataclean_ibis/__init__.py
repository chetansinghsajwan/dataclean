from dataclean import PluginInfo
from dataclean_ibis.catalog import IbisCatalog
from dataclean_ibis.dataframe import IbisDataFrame

info = PluginInfo(
    name="dataclean-ibis",
    catalog_types={
        IbisCatalog,
    },
    dataframe_types={
        IbisDataFrame,
    },
)
