"""Unified cleaner contract and role descriptors."""

import inspect
from abc import ABC, abstractmethod
from typing import Self

from pydantic import PrivateAttr, model_validator

from dataclean.engine.dataframe import DataFrame, DataType
from dataclean.types import StrictBaseModel

PRIMARY = "value"

# Supported scalar return types that engine writers accept
Scalar = str | bool | int | float | None


class ColumnRole(StrictBaseModel):
    """An input role required or optionally consumed by a cleaner."""

    key: str
    required: bool = True
    detector: "Cleaner | None" = None
    name_hints: tuple[str, ...] = ()


class Cleaner(StrictBaseModel, ABC):
    """Immutable, unified contract for single-column and multi-column cleaners."""

    tags: tuple[str, ...] = ()
    inplace: bool = True
    _input_roles: tuple[ColumnRole, ...] = PrivateAttr()
    _name: str = PrivateAttr()

    @model_validator(mode="after")
    def _set_name(self) -> Self:

        base = type(self).__name__
        object.__setattr__(
            self, "_name", f"{base}({', '.join(self.tags)})" if self.tags else base
        )
        return self

    @model_validator(mode="after")
    def _infer_roles(self) -> Self:
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

        # Private attrs on frozen models must be set via object.__setattr__
        object.__setattr__(self, "_input_roles", roles)
        return self

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

    def get_data_type_confidence(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        """Score confidence that this cleaner matches the given columns."""
        return 0
