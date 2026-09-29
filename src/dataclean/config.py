"""Global dataclean configuration: the default cleaners, catalogs, and settings.

Exposes a single module-level :data:`config` instance (a :class:`Config`)
that holds the registered cleaners, catalog types, dataframe engine
adapters, and presets used by :func:`dataclean.clean` and
:func:`dataclean.clean_paths` when explicit ones aren't supplied.
"""

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
    """Global, mutable configuration for the dataclean library.

    A single instance of this class (:data:`config`) is created at import
    time, pre-registered with all of the built-in cleaners, and used as the
    default source of cleaners/catalogs/plugins throughout the library
    unless overridden explicitly.

    Attributes:
        ignore_cols: Column names to skip during cleaning.
        cleaners: Registered :class:`~dataclean.cleaners.Cleaner` instances
            available for auto-detection/assignment. Pre-populated with the
            built-in cleaners in :meth:`__post_init__`.
        col_renamer: :class:`ColRenamer` used to normalize column names.
            Defaults to snake_case.
        plugin_loader: :class:`~dataclean.plugins.PluginLoader` used to
            discover and load installed plugins, or ``None`` to disable
            plugin loading.
        dataframe_apis: Registered :class:`~dataclean.engine.DataFrame`
            engine adapter types.
        auto_load_plugins: If True, plugins are loaded automatically before
            cleaning. Defaults to True.
        catalog_types: Registered :class:`~dataclean.engine.Catalog` types,
            kept sorted by descending priority so environment
            auto-detection tries the highest-priority catalog first.
        presets: Registered :class:`~dataclean.preset.Preset` instances.
        catalog: The default :class:`~dataclean.engine.Catalog` instance to
            use, or ``None`` if none is configured.
        inplace: If True, cleaning operations mutate dataframes in place.
            Defaults to True.
    """

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
        """Register all built-in cleaner types."""
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
        """Add a :class:`~dataclean.engine.DataFrame` engine adapter type, if not already present."""

        if api not in self.dataframe_apis:
            self.dataframe_apis.append(api)

    def register_cleaner(self, api: Cleaner) -> None:
        """Add a :class:`~dataclean.cleaners.Cleaner` instance, if not already present."""

        if api not in self.cleaners:
            self.cleaners.append(api)

    def register_catalog(self, catalog: type[Catalog]) -> None:
        """Add a :class:`~dataclean.engine.Catalog` type, keeping ``catalog_types`` sorted by descending priority."""

        import bisect

        if catalog not in self.catalog_types:
            bisect.insort_right(self.catalog_types, catalog, key=lambda c: -c.priority)

    def register_preset(self, preset: Preset) -> None:
        """Add a :class:`~dataclean.preset.Preset` instance, if not already present."""
        if preset not in self.presets:
            self.presets.append(preset)


config = Config()
"""The process-wide default :class:`Config` instance used by :mod:`dataclean`."""
