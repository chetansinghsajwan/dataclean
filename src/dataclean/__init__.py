"""dataclean - Data cleaning library with automatic column detection.

Re-exports the library's public API: the entrypoints for cleaning a
dataframe or a set of cataloged paths (:mod:`dataclean.clean`), the
built-in cleaners (:mod:`dataclean.cleaners`), column renaming
(:mod:`dataclean.col_renamer`), the global configuration object
(:mod:`dataclean.config`), the engine-agnostic dataframe/catalog
abstractions (:mod:`dataclean.engine`), the cleaning pipeline and its
exceptions (:mod:`dataclean.pipeline`), the plugin system
(:mod:`dataclean.plugins`), presets (:mod:`dataclean.preset`), and the
``checked`` runtime type-checking decorator (:mod:`dataclean.types`).
"""

from .clean import CleanPathResult, clean, clean_paths
from .cleaners import (
    PRIMARY,
    AddressCleaner,
    BoolCleaner,
    Cleaner,
    ColumnRole,
    CountryCleaner,
    DateTimeCleaner,
    EmailCleaner,
    EnumCleaner,
    GenderCleaner,
    NumericCleaner,
    PhoneCleaner,
    TextCleaner,
    UuidCleaner,
)
from .col_renamer import ColRenamer
from .config import config
from .engine import (
    Catalog,
    CatalogPriority,
    DataFrame,
    DataReader,
    DataType,
    DataWriter,
)
from .pipeline import Pipeline
from .pipeline.exceptions import (
    DatacleanError,
    PipelineConfigError,
)
from .plugins import PluginInfo, PluginLoader
from .preset import Preset
from .types import checked

__version__ = "1.0.0"
