from dataclasses import dataclass, field

from dataclean.cleaners import Cleaner
from dataclean.engine import Catalog, DataFrame
from dataclean.preset import Preset
from dataclean.types import checked


@checked
@dataclass
class PluginInfo:
    name: str
    cleaner_types: set[type[Cleaner]] = field(default_factory=set)
    dataframe_types: set[type[DataFrame]] = field(default_factory=set)
    catalog_types: set[type[Catalog]] = field(default_factory=set)
    presets: set[Preset] = field(default_factory=set)
