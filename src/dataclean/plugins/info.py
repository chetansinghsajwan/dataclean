from dataclasses import dataclass, field

from dataclean.cleaners import Cleaner
from dataclean.engine.dataframe import DataFrame
from dataclean.types import checked


@checked
@dataclass
class PluginInfo:
    name: str
    cleaner_types: set[type[Cleaner]] = field(default_factory=set)
    dataframe_types: set[type[DataFrame]] = field(default_factory=set)
