"""dataclean - Data cleaning library with automatic column detection."""

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
from .logs import LogLevel
from .pipeline import Pipeline
from .pipeline.exceptions import (
    DatacleanError,
    PipelineConfigError,
)
from .plugins import PluginInfo, PluginLoader
from .preset import Preset
from .types import checked

__version__ = "1.0.0"
