from collections.abc import Mapping
from dataclasses import dataclass

from dataclean.cleaners.base_cleaner import BaseCleaner
from dataclean.cleaners.group_cleaner import GroupCleaner


@dataclass(frozen=True)
class ColumnAssignment:
    """Assignment of a BaseCleaner to a specific column."""

    column: str
    cleaner: BaseCleaner
    confidence: float


@dataclass(frozen=True)
class GroupAssignment:
    """Assignment of a GroupCleaner to multiple columns via roles."""

    cleaner: GroupCleaner
    role_columns: Mapping[str, str]  # role.key -> actual raw column name
    confidence: float


@dataclass(frozen=True)
class ExecutionPlan:
    """Topologically sorted execution plan with waves."""

    waves: tuple[tuple[ColumnAssignment | GroupAssignment, ...], ...]
