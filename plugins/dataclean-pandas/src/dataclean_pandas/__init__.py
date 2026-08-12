from dataclean import PluginInfo
from dataclean_pandas.catalog import PandasCatalog
from dataclean_pandas.dataframe import PandasDataFrame

info = PluginInfo(
    name="dataclean-pandas",
    catalog_types={
        PandasCatalog,
    },
    dataframe_types={
        PandasDataFrame,
    },
)
