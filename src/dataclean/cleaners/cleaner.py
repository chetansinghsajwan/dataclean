"""Unified cleaner contract and role descriptors."""

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from dataclean.engine.dataframe import DataFrame, DataType
from dataclean.types import checked

PRIMARY: str = "value"


@checked
@dataclass(kw_only=True)
class Cleaner(ABC):
    """Immutable, unified contract for single-column and multi-column cleaners."""

    MAX_SCORE: float = 1.0
    MIN_SCORE: float = 0.0

    @dataclass
    class InputSchema:
        @dataclass
        class Column:
            key: str = PRIMARY
            required: bool = True
            detector: "Cleaner | None" = None
            name_hints: tuple[str, ...] = ()

        cols: tuple[Column, ...] = ()

    @dataclass
    class OutputSchema:
        @dataclass
        class Column:
            name: str | None = None
            dtype: DataType = DataType.STR
            roles: tuple[str, ...] = ()

        cols: tuple[Column, ...] = ()

    tags: tuple[str, ...] = ()
    inplace: bool = True
    _name: str = ""
    inputs: InputSchema = field(init=False)
    outputs: OutputSchema = field(init=False)

    def __post_init__(self) -> None:
        base = type(self).__name__
        self._name = f"{base}({', '.join(self.tags)})" if self.tags else base
        self.inputs = self._infer_inputs()
        self.outputs = self._outputs()

    def _infer_inputs(self) -> InputSchema:
        """Resolve and validate input schema once, at construction time."""

        declared_inputs = self._inputs()
        parameters = tuple(inspect.signature(self.clean_row).parameters.values())
        if any(parameter.kind is parameter.VAR_POSITIONAL for parameter in parameters):
            raise TypeError("clean_row must declare positional parameters explicitly")
        if any(parameter.kind is parameter.VAR_KEYWORD for parameter in parameters):
            raise TypeError("clean_row must not accept arbitrary keyword arguments")

        # Normalize inferred inputs: if there is exactly one positional parameter the
        # primary input role should be the canonical PRIMARY key (e.g. 'value') so
        # single-argument cleaners are consistently addressable.
        if len(parameters) == 1:
            parameter = parameters[0]
            inferred_cols = (
                Cleaner.InputSchema.Column(
                    key=PRIMARY,
                    required=parameter.default is inspect.Parameter.empty,
                ),
            )
        else:
            inferred_cols = tuple(
                Cleaner.InputSchema.Column(
                    key=(
                        PRIMARY if i == 0 and parameter.name == "v" else parameter.name
                    ),
                    required=parameter.default is inspect.Parameter.empty,
                )
                for i, parameter in enumerate(parameters)
            )

        # If explicit inputs were provided by the cleaner author, validate they
        # match the clean_row signature. If not provided, use the inferred inputs.
        if declared_inputs.cols:
            cols = declared_inputs.cols
            if len(cols) != len(parameters) or tuple(col.key for col in cols) != tuple(
                parameter.name for parameter in parameters
            ):
                raise TypeError(
                    "inputs must have the same keys and order as clean_row parameters"
                )
        else:
            cols = inferred_cols

        return Cleaner.InputSchema(cols=cols)

    @property
    def name(self) -> str:
        """Return the cleaner name."""
        return self._name

    @abstractmethod
    def clean_row(self, *values: str | None) -> str | None | tuple[str | None, ...]:
        pass

    def _inputs(self) -> InputSchema:
        """Return the input schema."""
        return Cleaner.InputSchema()

    def _outputs(self) -> OutputSchema:
        """Return the output schema."""
        return Cleaner.OutputSchema(cols=(Cleaner.OutputSchema.Column(),))

    def match_score(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        """Score confidence (0.0-1.0) that this cleaner matches the given columns."""
        return Cleaner.MIN_SCORE


ColumnRole = Cleaner.InputSchema.Column
