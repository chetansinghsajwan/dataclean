import importlib.metadata
import logging
from dataclasses import dataclass
from logging import Logger, getLogger

from dataclean.config import register_cleaner_api, register_dataframe_api
from dataclean.plugins.info import PluginInfo
from dataclean.types import checked

logging.basicConfig(level=logging.INFO)
pluginLogger = getLogger("PluginLoader")
pluginLogger.setLevel("DEBUG")


@checked
@dataclass
class PluginLoader:
    logger: Logger = pluginLogger

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

        package_name = package_name.replace("-", "_")
        module = importlib.import_module(package_name)

        plugin = module.info

        if type(plugin) is not PluginInfo:
            raise RuntimeError(
                "Plugin %s does not have a valid info object", package_name
            )

        self.logger.debug("\tRegistering dataframes...")
        for dataframe_type in plugin.dataframe_types:
            register_dataframe_api(dataframe_type)

        self.logger.debug("\tRegistering cleaners...")
        for cleaner_type in plugin.cleaner_types:
            register_cleaner_api(cleaner_type)

    def load_plugins(self) -> None:
        self.logger.info("Finding plugins...")
        plugins = self.find_plugins()

        for package_name in plugins:
            self.logger.info("Loading plugin: %s", package_name)
            self.load_plugin(package_name)
