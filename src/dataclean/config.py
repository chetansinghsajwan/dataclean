from dataclasses import dataclass, field
from typing import Any

from .cleaners import (
    AddressCleaner,
    BoolCleaner,
    Cleaner,
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
from .engine import Catalog, DataFrame
from .plugins import PluginLoader
from .preset import Preset
from .types import checked


@checked
@dataclass(kw_only=True)
class Config:
    ignore_cols: list[str] = field(default_factory=list)
    cleaners: list[Cleaner] = field(default_factory=list)
    col_renamer: ColRenamer = field(default_factory=lambda: ColRenamer(case="snake"))
    plugin_loader: PluginLoader | None = field(default_factory=PluginLoader)
    dataframe_apis: list[Any] = field(default_factory=list)
    auto_load_plugins: bool = True
    catalog_types: list[type[Catalog]] = field(default_factory=list)
    presets: list[Preset] = field(default_factory=list)
    catalog: Catalog | None = None
    inplace: bool = True

    def __post_init__(self) -> None:
        self.register_cleaner(AddressCleaner())
        self.register_cleaner(BoolCleaner())
        self.register_cleaner(CountryCleaner())
        self.register_cleaner(DateTimeCleaner())
        self.register_cleaner(EmailCleaner())
        self.register_cleaner(GenderCleaner())
        self.register_cleaner(NumericCleaner())
        self.register_cleaner(PhoneCleaner())
        self.register_cleaner(TextCleaner())
        self.register_cleaner(UuidCleaner())

    def register_dataframe(self, api: type[DataFrame]) -> None:

        if api not in self.dataframe_apis:
            self.dataframe_apis.append(api)

    def register_cleaner(self, api: Cleaner) -> None:

        if api not in self.cleaners:
            self.cleaners.append(api)

    def register_catalog(self, catalog: type[Catalog]) -> None:

        import bisect

        if catalog not in self.catalog_types:
            bisect.insort_right(self.catalog_types, catalog, key=lambda c: -c.priority)

    def register_preset(self, preset: Preset) -> None:
        if preset not in self.presets:
            self.presets.append(preset)


config = Config()
