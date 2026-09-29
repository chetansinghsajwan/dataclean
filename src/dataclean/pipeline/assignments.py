"""Data structures describing how cleaners are bound to dataframe columns."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from dataclean.cleaners import Cleaner
from dataclean.types import checked


@checked
@dataclass
class Assignment:
    """A cleaner assigned to raw input columns and resolved context outputs.

    Attributes:
        cleaner: The `Cleaner` instance bound to the input/context columns.
        role_columns: Mapping of the cleaner's input role keys (e.g.
            `PRIMARY`) to the raw dataframe column names that fill them.
        confidence: Match score (0.0-1.0) for this assignment, as produced by
            `Resolver`. A confidence of 1.0 indicates an explicit mapping.
        context_columns: Mapping of the cleaner's context role keys to the
            dataframe column names that supply them, as resolved by
            `DependencyResolver`. Empty until dependency resolution runs.
    """

    cleaner: Cleaner
    role_columns: Mapping[str, str]
    confidence: float
    context_columns: Mapping[str, str] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """Topologically sorted execution plan with independent execution waves.

    Attributes:
        waves: Ordered tuple of waves, where each wave is a tuple of
            `Assignment` objects that have no dependencies on one another and
            can be executed in any order (or concurrently) within that wave.
    """

    waves: tuple[tuple[Assignment, ...], ...]
