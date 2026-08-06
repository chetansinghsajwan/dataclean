"""Unified cleaner contract and role descriptors."""

import inspect
from abc import ABC, abstractmethod
from typing import Self

from pydantic import PrivateAttr, model_validator

from dataclean.engine.dataframe import DataFrame, DataType
from dataclean.types import StrictBaseModel

PRIMARY = "value"
type CellValue = str | int | float | bool


class ColumnRole(StrictBaseModel, frozen=True):  # ty: ignore[invalid-frozen-dataclass-subclass]
    """An input role required or optionally consumed by a cleaner."""

    key: str
    required: bool = True
    detector: "Cleaner | None" = None
    name_hints: tuple[str, ...] = ()


class Cleaner(StrictBaseModel, ABC, frozen=True):  # ty: ignore[invalid-frozen-dataclass-subclass]
    """Immutable, unified contract for single-column and multi-column cleaners."""

    tags: tuple[str, ...] = ()
    inplace: bool = True
    split_components: bool = False
    _input_roles: tuple[ColumnRole, ...] = PrivateAttr()
    _name: str = PrivateAttr()

    @model_validator(mode="after")
    def _set_name(self) -> Self:

        base = type(self).__name__
        self._name = f"{base}({', '.join(self.tags)})" if self.tags else base
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

        inferred_roles = tuple(
            ColumnRole(
                key=parameter.name,
                required=parameter.default is inspect.Parameter.empty,
            )
            for parameter in parameters
        )
        roles = declared_roles or inferred_roles
        if len(roles) != len(parameters) or tuple(role.key for role in roles) != tuple(
            parameter.name for parameter in parameters
        ):
            raise TypeError(
                "input_roles() must have the same keys and order as clean_row parameters"
            )
        self._input_roles = roles
        return self

    @property
    def name(self) -> str:
        """Return the cleaner name."""
        return self._name

    @abstractmethod
    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]:
        """Return the output schema."""

    @abstractmethod
    def clean_row(
        self, *values: CellValue | None
    ) -> CellValue | tuple[CellValue | None, ...] | None:
        """Clean one row using positional values in input-role order."""

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
