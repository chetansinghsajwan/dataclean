"""Discovers and loads installed dataclean plugin packages.

A plugin is any installed Python distribution whose name starts with
``dataclean-``. Each such package is expected to expose a module-level
``info`` attribute (a :class:`~dataclean.plugins.info.PluginInfo`) that this
loader reads and registers into the global
:class:`~dataclean.config.Config`.
"""

import importlib.metadata
import logging
from dataclasses import dataclass

from dataclean.types import checked

from .info import PluginInfo

_logger = logging.getLogger(__name__)


@checked
@dataclass
class PluginLoader:
    """Discovers installed ``dataclean-*`` packages and registers their contents."""

    def find_plugins(self) -> set[str]:
        """Return the distribution names of all installed ``dataclean-*`` packages."""

        # Get all installed distributions
        installed_packages = importlib.metadata.distributions()

        # Filter for packages starting with 'dataclean-'
        dataclean_packages = {
            dist.metadata["Name"]
            for dist in installed_packages
            if dist.metadata["Name"].startswith("dataclean-")
        }

        return dataclean_packages

    def load_plugin(self, package_name: str) -> None:
        """Import a plugin package and register its contents into the global config.

        Imports ``package_name`` (with hyphens replaced by underscores, per
        Python module naming), reads its module-level ``info`` attribute,
        and registers every dataframe type, cleaner, catalog, and preset it
        declares with :data:`dataclean.config.config`.

        Args:
            package_name: Distribution name of the plugin (e.g.
                ``"dataclean-foo"``), as returned by :meth:`find_plugins`.

        Raises:
            RuntimeError: If the imported module's ``info`` attribute is not
                a :class:`~dataclean.plugins.info.PluginInfo` instance.
        """

        from dataclean.config import config

        package_name = package_name.replace("-", "_")
        module = importlib.import_module(package_name)

        plugin = module.info

        if type(plugin) is not PluginInfo:
            raise RuntimeError(
                "Plugin %s does not have a valid info object", package_name
            )

        dataframe_count = len(plugin.dataframe_types)
        _logger.debug("\tRegistering %s dataframes...", dataframe_count)
        for dataframe_type in plugin.dataframe_types:
            config.register_dataframe(dataframe_type)

        cleaner_count = len(plugin.cleaner_types)
        _logger.debug("\tRegistering %s cleaners...", cleaner_count)
        for cleaner_type in plugin.cleaner_types:
            config.register_cleaner(cleaner_type)

        catalog_count = len(plugin.catalog_types)
        _logger.debug("\tRegistering %s catalogs...", catalog_count)
        for catalog_type in plugin.catalog_types:
            config.register_catalog(catalog_type)

        preset_count = len(plugin.presets)
        _logger.debug("\tRegistering %s presets...", preset_count)
        for preset in plugin.presets:
            config.register_preset(preset)

    def load_plugins(self) -> None:
        """Discover all installed plugins via :meth:`find_plugins` and load each one."""
        _logger.info("Finding plugins...")
        plugins = self.find_plugins()

        for package_name in plugins:
            _logger.info("Loading plugin: %s", package_name)
            self.load_plugin(package_name)
