"""Pipeline module for orchestrating data cleaning.

Exposes the public API for resolving `Cleaner` objects to dataframe columns,
resolving dependencies between them, and executing them in order via
`Pipeline`.
"""

from .assignments import Assignment, ExecutionPlan
from .entity_extractor import EntityExtractor
from .exceptions import (
    AmbiguousRoleError,
    CycleDetectedError,
    DatacleanError,
    DependencyResolutionError,
    MissingRequiredRoleError,
    PipelineConfigError,
)
from .pipeline import Pipeline
