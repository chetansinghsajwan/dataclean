# Writing a Custom Cleaner

None of the built-ins fit every column shape. This page walks through
subclassing `Cleaner` (`src/dataclean/cleaners/cleaner.py`), from the
simplest single-value case up to `AddressCleaner`'s multi-column pattern,
plus how to make your cleaner participate in auto-detection and how to test
it. Read [Concepts](concepts.md) first if you haven't — this page assumes
you know what `InputSchema`/`OutputSchema` and `match_score` are for.

## A minimal single-input cleaner

If `clean_row` takes a single positional parameter, `Cleaner` infers the
`InputSchema` for you — no need to override `_inputs()`:

```python
from dataclasses import dataclass
from dataclean import Cleaner


@dataclass
class UpperCaseCleaner(Cleaner):
    def clean_row(self, v: str | None) -> str | None:
        if not v:
            return None
        return v.strip().upper()
```

`UpperCaseCleaner().inputs.cols` will be a single column with key
`PRIMARY` (`"value"`), `required=True` (the parameter has no default).
Make a parameter optional the normal Python way — give it a default:

```python
def clean_row(self, v: str | None = None) -> str | None: ...
```

## A multi-input cleaner

For multiple named inputs, `clean_row`'s parameter names become the role
keys automatically. Override `_inputs()` only when you need to configure
`required`, `name_hints`, or a `detector` per role — and if you do, the keys
and order must exactly match `clean_row`'s parameters, or `Cleaner` raises a
`TypeError` at construction time. `AddressCleaner` is the reference example
in this codebase (`src/dataclean/cleaners/address_cleaner.py`):

```python
from dataclasses import dataclass
from typing import override
from dataclean import Cleaner


@dataclass
class FullNameCleaner(Cleaner):
    @override
    def _inputs(self) -> Cleaner.InputSchema:
        return Cleaner.InputSchema(
            cols=(
                Cleaner.InputSchema.Column(
                    key="first_name", name_hints=("first_name", "given_name")
                ),
                Cleaner.InputSchema.Column(
                    key="last_name",
                    required=False,
                    name_hints=("last_name", "surname"),
                ),
            )
        )

    def clean_row(
        self, first_name: str | None, last_name: str | None = None
    ) -> str | None:
        if not first_name:
            return None
        parts = [first_name.strip().title()]
        if last_name:
            parts.append(last_name.strip().title())
        return " ".join(parts)
```

`required=False` on a role means the pipeline will still assign this cleaner
even if no column matches that role — `clean_row` just receives `None` for
it. A **required** role with no matching column causes the resolver to skip
this cleaner entirely for that set of columns (see
[Auto-detection mechanics](concepts.md#auto-detection-mechanics)).

## Declaring outputs

Override `_outputs()` to name your output column(s), give them a `dtype`
(`DataType`), and — if another cleaner should be able to depend on this
value as a context input — tag them with a `roles` entry:

```python
from typing import override
from dataclean import Cleaner, DataType


class PostcodeCleaner(Cleaner):
    @override
    def _outputs(self) -> Cleaner.OutputSchema:
        return Cleaner.OutputSchema(
            cols=(
                Cleaner.OutputSchema.Column(
                    name="postcode", dtype=DataType.STR, roles=("postcode",)
                ),
            )
        )
```

If you don't override `_outputs()`, the default is a single unnamed STR
column (the pipeline reuses the input column's name and overwrites it).

## Making your cleaner auto-detectable: `match_score`

The base `match_score` always returns `0.0` — a cleaner that never overrides
it can only be used via an explicit `column_cleaners` mapping, never
auto-detection. Two patterns cover almost every case in this codebase:

**Cheap, name-only matching** (used by `EmailCleaner`, `PhoneCleaner`,
`CountryCleaner`, `UuidCleaner`, `DateTimeCleaner` — see
[Built-in Cleaners](cleaners.md) for exactly what each one checks):

```python
from typing import override
from dataclean import Cleaner
from dataclean.engine.dataframe import DataFrame


class ScoreCardCleaner(Cleaner):
    @override
    def match_score(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        assert len(cols) == 1
        return Cleaner.MAX_SCORE if "score" in cols[0].lower() else Cleaner.MIN_SCORE
```

**Value-sampling fallback**, for when the column name alone isn't enough —
this is the pattern `EnumCleaner` implements and `BoolCleaner`/`GenderCleaner`
inherit unchanged. It queries the actual data through the `DataFrame` fluent
API for up to the 100 most frequent distinct non-null values, then scores by
the frequency-weighted fraction that match:

```python
from dataclean.engine.dataframe import Aggregators


def match_score(self, df: DataFrame, cols: tuple[str, ...]) -> float:
    assert len(cols) == 1
    col = cols[0]
    rows = (
        df
        .select(col)
        .strip()
        .nullif()
        .filter_null()
        .group_by([col])
        .agg(Aggregators.count)
        .order_by(col, desc=True)
        .limit(100)
        .collect()
    )
    total = sum(count for _, count in rows)
    if not total:
        return Cleaner.MIN_SCORE
    matched = sum(count for value, count in rows if self._is_valid(value))
    return matched / total
```

## Testing your cleaner

`clean_row` needs no `DataFrame` at all — test it directly. `match_score`
that touches `df` needs a mock; the pattern used throughout this codebase's
own test suite is `unittest.mock.MagicMock(spec=DataFrame)`, with the query
chain's terminal `.collect()` stubbed to return your fake `(value, count)`
rows. The reusable fixture in `tests/cleaners/conftest.py`,
`mock_df_with_value_counts`, is the canonical way to do this — copy its
pattern for your own cleaner's tests:

```python
def test_my_cleaner_value_sampling(mock_df_with_value_counts):
    cleaner = MyCleaner()
    mock_df = mock_df_with_value_counts([("yes", 7), ("no", 3)])
    assert cleaner.match_score(mock_df, ("some_col",)) == 1.0
```

For a cheap name-only `match_score`, a plain `MagicMock(spec=DataFrame)` with
no chain stubbed is enough, since `df` is never actually touched.

## Registering it

A cleaner only participates in `dataclean.clean(df)` if it's in
`config.cleaners`:

```python
from dataclean import config

config.register_cleaner(MyCleaner())
```

Or pass it explicitly to a one-off `Pipeline`:

```python
from dataclean import Pipeline

Pipeline(cleaners=(MyCleaner(),), auto_detect=True).fit_transform(df)
```

See [Configuration](configuration.md) for everything else `Config` lets you
register.
