import importlib.metadata
from dataclasses import dataclass, field
from logging import Logger

from dataclean import logs
from dataclean.plugins.info import PluginInfo
from dataclean.types import checked


@checked
@dataclass
class PluginLoader:
    _logger: Logger = field(init=False)

    def __post_init__(self) -> None:
        self._logger = logs.get_logger("PluginLoader")

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

        self._logger.debug("\tRegistering dataframes...")
        for dataframe_type in plugin.dataframe_types:
            config.register_dataframe(dataframe_type)

        self._logger.debug("\tRegistering cleaners...")
        for cleaner_type in plugin.cleaner_types:
            config.register_cleaner(cleaner_type)

        self._logger.debug("\tRegistering catalogs...")
        for catalog_type in plugin.catalog_types:
            config.register_catalog(catalog_type)

    def load_plugins(self) -> None:
        self._logger.info("Finding plugins...")
        plugins = self.find_plugins()

        for package_name in plugins:
            self._logger.info("Loading plugin: %s", package_name)
            self.load_plugin(package_name)
