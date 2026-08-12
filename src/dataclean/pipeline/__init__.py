"""Pipeline module for orchestrating data cleaning."""

from .assignments import Assignment, ExecutionPlan
from .catalog import (
    Catalog as PipelineCatalog,
    DefaultCatalog as PipelineDefaultCatalog,
)
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
