"""Plugin entry point for the CCH CRM column presets."""

from dataclean import PluginInfo

from .preset import CchCrmPreset

# What dataclean's plugin loader reads to find the CCH CRM preset pieces.
info = PluginInfo(
    name="dataclean-cch-crm",
    presets={
        CchCrmPreset(),
    },
)
