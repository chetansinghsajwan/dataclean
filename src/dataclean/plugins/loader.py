import importlib.metadata
import logging
from dataclasses import dataclass

from dataclean.types import checked

from .info import PluginInfo

_logger = logging.getLogger(__name__)


@checked
@dataclass
class PluginLoader:
    def find_plugins(self) -> set[str]:

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
        _logger.info("Finding plugins...")
        plugins = self.find_plugins()

        for package_name in plugins:
            _logger.info("Loading plugin: %s", package_name)
            self.load_plugin(package_name)
