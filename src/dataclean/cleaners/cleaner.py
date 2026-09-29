"""Unified cleaner contract and role descriptors.

Defines the ``Cleaner`` abstract base dataclass that every column-cleaning
strategy in the pipeline implements, along with the ``InputSchema`` and
``OutputSchema`` descriptors used to declare which column roles a cleaner
consumes and produces.
"""

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from dataclean.engine.dataframe import DataFrame, DataType
from dataclean.types import checked

# Canonical input/output key used for single-argument cleaners, so that
# single-column cleaners are consistently addressable by this role name.
PRIMARY: str = "value"


@checked
@dataclass(kw_only=True)
class Cleaner(ABC):
    """Base contract for column-cleaning strategies in the pipeline.

    A cleaner normalizes and/or validates the values of one or more input
    columns and produces one or more output columns. Concrete subclasses
    implement ``clean_row`` to transform a single row's values, and may
    override ``_inputs``/``_outputs`` to declare the input/output schema
    (roles, name hints, required-ness, dtypes) and ``match_score`` to report
    how confident the cleaner is that it applies to a given set of columns.

    Instances behave as immutable dataclasses; the input and output schemas
    are resolved once in ``__post_init__`` and cached on ``inputs``/
    ``outputs``.

    Attributes:
        MAX_SCORE: Upper bound for match_score confidence values.
        MIN_SCORE: Lower bound for match_score confidence values.
        tags: Optional labels distinguishing multiple instances of the same
            cleaner class; included in the cleaner's display name.
        inplace: Whether this cleaner's outputs should replace the input
            column(s) in place rather than being appended as new columns.
        inputs: The resolved input schema, computed from ``_inputs()`` and
            validated against the ``clean_row`` signature.
        outputs: The resolved output schema, computed from ``_outputs()``.
    """

    MAX_SCORE: float = 1.0
    MIN_SCORE: float = 0.0

    @dataclass
    class InputSchema:
        """Describes the input columns a cleaner expects to receive.

        Attributes:
            cols: The ordered input column descriptors, one per positional
                parameter of ``clean_row``.
        """

        @dataclass
        class Column:
            """Describes a single input column role.

            Attributes:
                key: The role/parameter name this column binds to; matches
                    the corresponding ``clean_row`` parameter name.
                required: Whether a value must be supplied for this column.
                detector: An optional cleaner used to detect/validate
                    whether a candidate dataframe column matches this role.
                name_hints: Candidate column-name keywords that suggest a
                    dataframe column fills this role.
            """

            key: str = PRIMARY
            required: bool = True
            detector: "Cleaner | None" = None
            name_hints: tuple[str, ...] = ()

        cols: tuple[Column, ...] = ()

    @dataclass
    class OutputSchema:
        """Describes the output columns a cleaner produces.

        Attributes:
            cols: The ordered output column descriptors.
        """

        @dataclass
        class Column:
            """Describes a single output column.

            Attributes:
                name: Suggested name for the output column, or None to
                    reuse the input column's name.
                dtype: The data type of the produced output column.
                roles: Semantic role labels (e.g. "country", "postcode")
                    identifying what this output column represents.
            """

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
        """Compute the cleaner's display name and resolve its input/output schemas."""
        base = type(self).__name__
        self._name = f"{base}({', '.join(self.tags)})" if self.tags else base
        self.inputs = self._infer_inputs()
        self.outputs = self._outputs()

    def _infer_inputs(self) -> InputSchema:
        """Resolve and validate the input schema from clean_row's signature.

        If the subclass does not declare an explicit input schema via
        ``_inputs()``, the schema is inferred from ``clean_row``'s
        positional parameters: a single parameter is normalized to use the
        canonical ``PRIMARY`` key, and multiple parameters use their
        parameter names as keys. A column's ``required`` flag reflects
        whether the corresponding parameter has no default value.

        If an explicit input schema is declared, it must match the
        ``clean_row`` signature exactly (same keys, in the same order).

        Returns:
            The resolved input schema.

        Raises:
            TypeError: If ``clean_row`` declares ``*args`` or ``**kwargs``,
                or if a declared input schema does not match the
                ``clean_row`` parameters.
        """

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
        """Return the cleaner's display name (class name plus any tags)."""
        return self._name

    @abstractmethod
    def clean_row(self, *values: str | None) -> str | None | tuple[str | None, ...]:
        """Clean a single row's input value(s).

        Subclasses override this with concrete positional parameters (not
        ``*values``); the parameter names and defaults are introspected to
        infer the input schema (see ``_infer_inputs``).

        Args:
            *values: The raw input value(s) for this row, one per input
                column.

        Returns:
            The cleaned value for a single-output cleaner, or a tuple of
            cleaned values for a multi-output cleaner.
        """
        pass

    def _inputs(self) -> InputSchema:
        """Return the declared input schema, if any.

        Subclasses that need custom ``required``/``name_hints``/
        ``detector`` metadata override this; otherwise the schema is
        inferred from ``clean_row``'s signature. Defaults to an empty
        schema, meaning "infer from clean_row".
        """
        return Cleaner.InputSchema()

    def _outputs(self) -> OutputSchema:
        """Return the output schema produced by this cleaner.

        Defaults to a single unnamed STR output column; subclasses override
        this to declare their actual output columns, dtypes, and roles.
        """
        return Cleaner.OutputSchema(cols=(Cleaner.OutputSchema.Column(),))

    def match_score(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        """Score how confident this cleaner is that it applies to cols.

        Args:
            df: The dataframe containing the candidate column(s).
            cols: The candidate column name(s) being evaluated.

        Returns:
            A confidence score between MIN_SCORE and MAX_SCORE (inclusive).
            The base implementation always returns MIN_SCORE; subclasses
            override this to inspect column names and/or sampled values.
        """
        return Cleaner.MIN_SCORE


# Convenience alias for referring to Cleaner.InputSchema.Column from outside
# the Cleaner class.
ColumnRole = Cleaner.InputSchema.Column
