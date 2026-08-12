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
    catalog_types: set[type[Catalog]] = field(default_factory=set)
    catalog: Catalog | None = None
    inplace: bool = True

    log_level: LogLevel = LogLevel.INFO
    log_format: str | None = None
    log_handlers: list[logging.Handler] | None = None
    logger_provider: LoggerProvider | None = None


config = Config()


@checked
def register_dataframe(api: type[DataFrame]) -> None:
    """Register a dataframe API adapter globally.

    Engines should call this at import time to make themselves available to
    consumers without requiring manual registration. Duplicate registrations
    are ignored.
    """

    if api not in config.dataframe_apis:
        config.dataframe_apis.append(api)


@checked
def register_cleaner(api: Cleaner) -> None:
    """Register a cleaner API adapter globally.

    Engines should call this at import time to make themselves available to
    consumers without requiring manual registration. Duplicate registrations
    are ignored.
    """

    if api not in config.cleaners:
        config.cleaners.append(api)


@checked
def register_catalog(api: type[Catalog]) -> None:
    """Register a catalog API adapter globally.

    Engines should call this at import time to make themselves available to
    consumers without requiring manual registration. Duplicate registrations
    are ignored.
    """

    if api not in config.catalog_types:
        config.catalog_types.add(api)
