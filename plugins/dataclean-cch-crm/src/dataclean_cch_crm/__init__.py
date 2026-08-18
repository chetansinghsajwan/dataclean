from dataclean import PluginInfo

from .preset import CchCrmPreset

info = PluginInfo(
    name="dataclean-cch-crm",
    presets={
        CchCrmPreset(),
    },
)
