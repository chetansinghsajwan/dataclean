"""Exception hierarchy for pipeline configuration and execution."""


class DatacleanError(Exception):
    """Base exception for dataclean errors."""

    pass


class PipelineConfigError(DatacleanError):
    """Raised when pipeline configuration is invalid."""

    pass


class GroupCleanerResolutionError(PipelineConfigError):
    """Raised when group cleaner resolution fails."""

    pass


class DependencyResolutionError(PipelineConfigError):
    """Raised when dependency resolution fails (cycles, missing roles, ambiguity)."""

    pass


class CycleDetectedError(DependencyResolutionError):
    """Raised when a cycle is detected in the dependency graph."""

    pass


class MissingRequiredRoleError(DependencyResolutionError):
    """Raised when a required context role cannot be matched."""

    pass


class AmbiguousRoleError(DependencyResolutionError):
    """Raised when a role has multiple equally valid producers and cannot be disambiguated."""

    pass
