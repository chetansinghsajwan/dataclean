import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from dataclean.cleaners.cleaner import Cleaner
from dataclean.col_renamer import ColRenamer
from dataclean.engine.catalog import Catalog
from dataclean.engine.dataframe import DataFrame
from dataclean.logs import LogLevel
from dataclean.plugins.loader import PluginLoader
from dataclean.types import checked

LoggerProvider = Callable[[str], logging.Logger]


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
    catalog: Catalog | None = None
    inplace: bool = True

    log_level: LogLevel = LogLevel.INFO
    log_format: str | None = None
    log_handlers: list[logging.Handler] | None = None
    logger_provider: LoggerProvider | None = None

    def register_dataframe(self, api: type[DataFrame]) -> None:

        if api not in self.dataframe_apis:
            self.dataframe_apis.append(api)

    def register_cleaner(self, api: Cleaner) -> None:

        if api not in self.cleaners:
            self.cleaners.append(api)

    def register_catalog(self, catalog: type[Catalog]) -> None:

        import bisect

        if catalog not in self.catalog_types:
            bisect.insort_right(self.catalog_types, catalog, key=lambda c: c.priority)


config = Config()
