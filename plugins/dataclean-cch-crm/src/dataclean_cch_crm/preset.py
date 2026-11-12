"""Column preset for CCH CRM tables."""

from typing import override

from dataclean import Cleaner, Preset, checked


@checked
class CchCrmPreset(Preset):
    """Placeholder preset for CCH CRM tables; it never matches and sets no cleaners yet."""

    @override
    def match(self, ctx: Preset.MatchContext) -> float:

        return 0.0

    @override
    def get(self) -> dict[str, Cleaner]:
        return {}
