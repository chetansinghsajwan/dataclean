"""Ibis-backed implementation of the dataclean ``DataFrame`` engine API."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, override

import ibis
import ibis.expr.datatypes as dt
import pandas as pd

from dataclean import DataFrame, DataReader, DataType, DataWriter
from dataclean.engine.dataframe import Aggregator, Aggregators
from dataclean.types import checked

_TO_IBIS_DTYPE: dict[DataType, dt.DataType] = {
    DataType.STR: dt.String(),
    DataType.BOOL: dt.Boolean(),
    DataType.INT: dt.Int64(),
    DataType.FLOAT: dt.Float32(),
    DataType.DOUBLE: dt.Float64(),
}


def _from_ibis_dtype(dtype: dt.DataType) -> DataType:
    """Map an Ibis dtype instance to dataclean's engine-agnostic DataType."""
    if dtype.is_boolean():
        return DataType.BOOL
    if dtype.is_integer():
        return DataType.INT
    if dtype.is_floating():
        return DataType.DOUBLE if isinstance(dtype, dt.Float64) else DataType.FLOAT
    return DataType.STR


def _build_scalar_udf(
    expr: Callable[..., Any],
    n_inputs: int,
    output_names: tuple[str, ...],
    return_type: dt.DataType,
) -> Callable[..., Any]:
    """Wrap an arbitrary ``*values``-shaped callable as an Ibis scalar UDF.

    ``ibis.udf.scalar.python`` inspects the wrapped function's signature and
    requires every parameter and the return value to be annotated with a
    fixed arity (no ``*args``). Cleaner callables have no such fixed,
    introspectable signature, so a small fixed-arity pass-through wrapper is
    synthesized here (one string parameter per input column) and decorated
    instead of ``expr`` directly.
    """
    params = ", ".join(f"a{i}" for i in range(n_inputs))
    if len(output_names) == 1:
        body = f"return _expr({params})"
    else:
        body = f"return dict(zip(_names, _expr({params}), strict=True))"

    source = f"def _wrapper({params}):\n    {body}\n"
    namespace: dict[str, Any] = {"_expr": expr, "_names": output_names}
    exec(source, namespace)  # noqa: S102 - builds a typed shim around a known callable
    wrapper_fn = namespace["_wrapper"]
    wrapper_fn.__annotations__ = {
        **{f"a{i}": str | None for i in range(n_inputs)},
        "return": return_type,
    }
    return ibis.udf.scalar.python(wrapper_fn)


@checked
@dataclass
class IbisDataFrame(DataFrame):
    """DataFrame engine adapter wrapping a lazy ``ibis.Table`` expression.

    Generic over any Ibis backend (DuckDB is the default/tested one via
    :class:`dataclean_ibis.catalog.IbisCatalog`). Pure/functional methods
    return a new :class:`IbisDataFrame` wrapping a new lazy expression, since
    Ibis tables are immutable; "mutating" methods reassign ``self.df`` to a
    new expression rather than mutating it, matching the same convention the
    lazy PySpark/Databricks adapter uses.
    """

    df: ibis.Table
    _cols: tuple[tuple[str, DataType], ...] = ()
    _group_keys: tuple[str, ...] = ()

    def __post_init__(self):
        self._update_cols()

    @staticmethod
    @override
    def supports(df: Any) -> bool:
        return isinstance(df, ibis.Table)

    @override
    def cols(self) -> tuple[tuple[str, DataType], ...]:
        return self._cols

    def _update_cols(self) -> None:
        self._cols = tuple(
            (name, _from_ibis_dtype(dtype)) for name, dtype in self.df.schema().items()
        )

    @override
    def rename_cols(self, rename_map: Mapping[str, str]) -> None:
        # dataclean's rename_map is old -> new; ibis.Table.rename() expects new -> old.
        inverted = {new: old for old, new in rename_map.items()}
        self.df = self.df.rename(inverted)
        self._update_cols()

    @override
    def read_cols(self, readers: Iterable[DataReader]) -> None:
        for reader in readers:
            if not reader.cols:
                continue

            pdf = self.df.select(*reader.cols).to_pandas()
            for row in pdf.itertuples(index=False, name=None):
                reader.fn(*row)

    @override
    def write_cols(self, writers: Iterable[DataWriter]) -> None:
        for writer in writers:
            if not writer.write_cols:
                continue

            if not callable(writer.expr):
                updates = {
                    name: ibis.literal(writer.expr, type=_TO_IBIS_DTYPE[dtype])
                    for name, dtype in writer.write_cols
                }
                self.df = self.df.mutate(**updates)
                continue

            input_exprs = [self.df[col].cast(dt.String()) for col in writer.read_cols]

            if len(writer.write_cols) == 1:
                write_col, write_dtype = writer.write_cols[0]
                udf = _build_scalar_udf(
                    writer.expr,
                    n_inputs=len(writer.read_cols),
                    output_names=(write_col,),
                    return_type=_TO_IBIS_DTYPE[write_dtype],
                )
                self.df = self.df.mutate(**{write_col: udf(*input_exprs)})
            else:
                output_names = tuple(name for name, _ in writer.write_cols)
                struct_type = dt.Struct(
                    {name: _TO_IBIS_DTYPE[dtype] for name, dtype in writer.write_cols}
                )
                udf = _build_scalar_udf(
                    writer.expr,
                    n_inputs=len(writer.read_cols),
                    output_names=output_names,
                    return_type=struct_type,
                )
                temp_col = "_dataclean_ibis_write_struct"
                self.df = self.df.mutate(**{temp_col: udf(*input_exprs)})
                self.df = self.df.mutate(
                    **{name: self.df[temp_col][name] for name in output_names}
                ).drop(temp_col)

            cast_map = {
                name: _TO_IBIS_DTYPE[dtype] for name, dtype in writer.write_cols
            }
            self.df = self.df.cast(cast_map)

        self._update_cols()

    @override
    def remove_cols(self, cols: Iterable[str]) -> None:
        self.df = self.df.drop(*cols)
        self._update_cols()

    @override
    def cast_cols(self, cols: Mapping[str, DataType]) -> None:
        overrides = {name: _TO_IBIS_DTYPE[dtype] for name, dtype in cols.items()}
        self.df = self.df.cast(overrides)
        self._update_cols()

    @override
    def group_by(self, cols: Iterable[str]) -> "IbisDataFrame":
        # Deliberately does not touch self.df: real per-group aggregation
        # (e.g. real counts) requires the group structure to still be intact
        # when agg() runs, so grouping stays purely metadata until then.
        return IbisDataFrame(df=self.df, _group_keys=tuple(cols))

    @override
    def agg(
        self, cols: Mapping[str, Aggregator] | Iterable[Aggregator] | Aggregator
    ) -> "IbisDataFrame":
        group_keys = list(self._group_keys)

        if cols is Aggregators.count:
            result = self.df.aggregate(by=group_keys, count=self.df.count())
            return IbisDataFrame(df=result)

        if isinstance(cols, Mapping):
            if cols and all(agg is Aggregators.count for agg in cols.values()):
                metrics = {name: self.df.count() for name in cols}
                result = self.df.aggregate(by=group_keys, **metrics)
                return IbisDataFrame(df=result)
            return self._agg_via_pandas_fallback(cols, group_keys)

        if callable(cols):
            return self._agg_via_pandas_fallback({"agg_0": cols}, group_keys)

        aggregators = list(cols)
        if aggregators and all(agg is Aggregators.count for agg in aggregators):
            result = self.df.aggregate(by=group_keys, count=self.df.count())
            return IbisDataFrame(df=result)
        return self._agg_via_pandas_fallback(
            {f"agg_{i}": agg for i, agg in enumerate(aggregators)}, group_keys
        )

    def _agg_via_pandas_fallback(
        self, named_aggregators: Mapping[str, Aggregator], group_keys: list[str]
    ) -> "IbisDataFrame":
        # Aggregators.count is the only Aggregator constructed anywhere in the
        # real codebase; any other aggregator has no lazy Ibis translation
        # available in general (Aggregator = Callable is fully generic), so
        # it is handled by materializing and delegating to pandas' own agg(),
        # exactly matching PandasDataFrame's (already eager) behavior here.
        pdf = self.df.to_pandas()
        if group_keys:
            result_pdf = pdf.groupby(group_keys, as_index=False).agg(named_aggregators)
        else:
            result_pdf = pdf.agg(named_aggregators)
            if not isinstance(result_pdf, pd.DataFrame):
                result_pdf = pd.DataFrame([result_pdf])
        return IbisDataFrame(df=ibis.memtable(result_pdf))

    @override
    def distinct(self, cols: Iterable[str] | None = None) -> "IbisDataFrame":
        on = list(cols) if cols is not None else None
        return IbisDataFrame(df=self.df.distinct(on=on, keep="first"))

    @override
    def count(self) -> int:
        return int(self.df.count().to_pandas())

    @override
    def collect(self) -> list[tuple[Any, ...]]:
        pdf = self.df.to_pandas()
        return [tuple(row) for row in pdf.itertuples(index=False, name=None)]

    @override
    def select(self, cols: str | Iterable[str]) -> "IbisDataFrame":
        cols_list = [cols] if isinstance(cols, str) else list(cols)
        return IbisDataFrame(df=self.df.select(*cols_list))

    def _resolve_string_cols(self, cols: str | Iterable[str] | None) -> list[str]:
        if cols is None:
            return [name for name, dtype in self.cols() if dtype == DataType.STR]
        return [cols] if isinstance(cols, str) else list(cols)

    @override
    def strip(self, cols: str | Iterable[str] | None = None) -> "IbisDataFrame":
        target_cols = self._resolve_string_cols(cols)
        result = self.df.mutate(**{c: self.df[c].strip() for c in target_cols})
        return IbisDataFrame(df=result)

    @override
    def nullif(self, cols: str | Iterable[str] | None = None) -> "IbisDataFrame":
        target_cols = self._resolve_string_cols(cols)
        result = self.df.mutate(**{c: self.df[c].nullif("") for c in target_cols})
        return IbisDataFrame(df=result)

    @override
    def order_by(
        self, cols: str | Iterable[str], desc: bool = False
    ) -> "IbisDataFrame":
        cols_list = [cols] if isinstance(cols, str) else list(cols)
        order_exprs = [ibis.desc(c) if desc else ibis.asc(c) for c in cols_list]
        return IbisDataFrame(df=self.df.order_by(*order_exprs))

    @override
    def limit(self, n: int) -> "IbisDataFrame":
        return IbisDataFrame(df=self.df.limit(n))

    @override
    def filter_null(self, cols: str | Iterable[str] | None = None) -> "IbisDataFrame":
        target_cols = (
            [cols]
            if isinstance(cols, str)
            else list(cols)
            if cols is not None
            else list(self.col_names())
        )
        result = self.df
        for c in target_cols:
            result = result.filter(result[c].notnull())
        return IbisDataFrame(df=result)
