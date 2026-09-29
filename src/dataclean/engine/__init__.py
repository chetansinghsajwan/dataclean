"""Engine abstractions: the DataFrame API and the Catalog data-source API.

Re-exports the public types used by the rest of dataclean to remain
agnostic of any specific dataframe engine (pandas, PySpark, etc.) or
storage backend.
"""

from .catalog import Catalog, CatalogPriority
from .dataframe import DataFrame, DataReader, DataType, DataWriter
