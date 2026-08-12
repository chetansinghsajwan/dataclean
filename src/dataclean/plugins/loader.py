import importlib.metadata
from dataclasses import dataclass, field
from logging import Logger

from dataclean.types import checked

from .info import PluginInfo


@checked
@dataclass
class PluginLoader:
    _logger: Logger | None = field(init=False, default=None)

    @property
    def logger(self) -> Logger:
        if self._logger is None:
            from dataclean.config import config

            self._logger = config.get_logger("PluginLoader")

        return self._logger

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

        self.logger.debug("\tRegistering dataframes...")
        for dataframe_type in plugin.dataframe_types:
            config.register_dataframe(dataframe_type)

        self.logger.debug("\tRegistering cleaners...")
        for cleaner_type in plugin.cleaner_types:
            config.register_cleaner(cleaner_type)

        self.logger.debug("\tRegistering catalogs...")
        for catalog_type in plugin.catalog_types:
            config.register_catalog(catalog_type)

    def load_plugins(self) -> None:
        self.logger.info("Finding plugins...")
        plugins = self.find_plugins()

        for package_name in plugins:
            self.logger.info("Loading plugin: %s", package_name)
            self.load_plugin(package_name)
