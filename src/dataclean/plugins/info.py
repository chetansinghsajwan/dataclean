"""Declarative description of what a dataclean plugin package provides."""

from dataclasses import dataclass, field

from dataclean.cleaners import Cleaner
from dataclean.engine import Catalog, DataFrame
from dataclean.preset import Preset
from dataclean.types import checked


@checked
@dataclass
class PluginInfo:
    """Manifest of the components a plugin package registers with dataclean.

    A plugin package is expected to expose a module-level ``info`` object of
    this type (see :meth:`dataclean.plugins.loader.PluginLoader.load_plugin`),
    listing every extension point it contributes so the loader can register
    each one with the global :class:`~dataclean.config.Config`.

    Attributes:
        name: Human-readable name of the plugin.
        cleaner_types: :class:`~dataclean.cleaners.Cleaner` subclasses this
            plugin provides.
        dataframe_types: :class:`~dataclean.engine.DataFrame` subclasses
            (engine adapters) this plugin provides.
        catalog_types: :class:`~dataclean.engine.Catalog` subclasses this
            plugin provides.
        presets: :class:`~dataclean.preset.Preset` instances this plugin
            provides.
    """

    name: str
    cleaner_types: set[type[Cleaner]] = field(default_factory=set)
    dataframe_types: set[type[DataFrame]] = field(default_factory=set)
    catalog_types: set[type[Catalog]] = field(default_factory=set)
    presets: set[Preset] = field(default_factory=set)
