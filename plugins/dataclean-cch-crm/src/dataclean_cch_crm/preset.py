from typing import override

from dataclean import Cleaner, Preset, checked


@checked
class CchCrmPreset(Preset):
    @override
    def match(self, ctx: Preset.MatchContext) -> float:

        return 0.0

    @override
    def get(self) -> dict[str, Cleaner]:
        return {}
