"""Unified cleaner contract and role descriptors."""

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass

from dataclean.engine.dataframe import DataFrame, DataType
from dataclean.types import checked

PRIMARY: str = "value"


@checked
@dataclass
class ColumnRole:
    """An input role required or optionally consumed by a cleaner."""

    key: str
    required: bool = True
    detector: "Cleaner | None" = None
    name_hints: tuple[str, ...] = ()


@checked
@dataclass
class Cleaner(ABC):
    """Immutable, unified contract for single-column and multi-column cleaners."""

    tags: tuple[str, ...] = ()
    inplace: bool = True
    _input_roles: tuple[ColumnRole, ...] = ()
    _name: str = ""

    def __post_init__(self) -> None:
        base = type(self).__name__
        self._name = f"{base}({', '.join(self.tags)})" if self.tags else base
        self._input_roles = self._infer_roles()

    def _infer_roles(self) -> tuple[ColumnRole, ...]:
        """Resolve and validate input roles once, at construction time."""

        declared_roles = self.input_roles()
        parameters = tuple(inspect.signature(self.clean_row).parameters.values())
        if any(parameter.kind is parameter.VAR_POSITIONAL for parameter in parameters):
            raise TypeError("clean_row must declare positional parameters explicitly")
        if any(parameter.kind is parameter.VAR_KEYWORD for parameter in parameters):
            raise TypeError("clean_row must not accept arbitrary keyword arguments")

        # Normalize inferred roles: if there is exactly one positional parameter the
        # primary input role should be the canonical PRIMARY key (e.g. 'value') so
        # single-argument cleaners are consistently addressable.
        if len(parameters) == 1:
            parameter = parameters[0]
            inferred_roles = (
                ColumnRole(
                    key=PRIMARY,
                    required=parameter.default is inspect.Parameter.empty,
                ),
            )
        else:
            inferred_roles = tuple(
                ColumnRole(
                    key=(
                        PRIMARY if i == 0 and parameter.name == "v" else parameter.name
                    ),
                    required=parameter.default is inspect.Parameter.empty,
                )
                for i, parameter in enumerate(parameters)
            )
        # If explicit roles were provided by the cleaner author, validate they
        # match the clean_row signature. If not provided, use the inferred roles
        # (which may normalize the single-argument primary role to PRIMARY).
        if declared_roles:
            roles = declared_roles
            if len(roles) != len(parameters) or tuple(
                role.key for role in roles
            ) != tuple(parameter.name for parameter in parameters):
                raise TypeError(
                    "input_roles() must have the same keys and order as clean_row parameters"
                )
        else:
            roles = inferred_roles

        return roles

    @property
    def name(self) -> str:
        """Return the cleaner name."""
        return self._name

    @abstractmethod
    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]:
        """Return the output schema."""

    @abstractmethod
    def clean_row(self, *values: str | None) -> str | None | tuple[str | None, ...]:
        pass

    def input_roles(self) -> tuple[ColumnRole, ...]:
        """Describe required inputs; inferred from ``clean_row`` by default."""
        return ()

    @property
    def resolved_input_roles(self) -> tuple[ColumnRole, ...]:
        """Return construction-time input-role metadata."""
        return self._input_roles

    def provided_roles(self) -> tuple[str, ...]:
        """Semantic role(s) this cleaner's output represents."""
        return ()

    def match_score(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        """Score confidence (0.0-1.0) that this cleaner matches the given columns."""
        return 0.0
