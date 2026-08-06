from collections.abc import Mapping
from dataclasses import dataclass, field

from dataclean.cleaners.cleaner import Cleaner


@dataclass(frozen=True)
class Assignment:
    """A cleaner assigned to raw input columns and resolved context outputs."""

    cleaner: Cleaner
    role_columns: Mapping[str, str]
    confidence: float
    context_columns: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionPlan:
    """Topologically sorted execution plan with independent execution waves."""

    waves: tuple[tuple[Assignment, ...], ...]
