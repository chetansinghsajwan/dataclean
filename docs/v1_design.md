# Dataclean Design V1 (Single Cleaner Design)

Scope: v1.0 ships as pure Python. Rust core migration begins after 1.0 — see
`DESIGN_PLAN.md`. This document supersedes the earlier
`Cleaner`/`BaseCleaner`/`GroupCleaner` 3-class split described in
`V1_PYTHON_DESIGN.md` — all cleaners are now a single unified class.

## 1. Goals

- User-friendly, unambiguous, beginner-friendly API
- Object-oriented, no duplicated logic
- Cleaners are immutable, constructed once, precompute at construction
- Automatic column → cleaner assignment with graceful degradation, never silent
  wrong guesses
- No per-row allocation overhead (dict-building, etc.)

## 2. Single Unified `Cleaner` Class

A "simple" cleaner is just a `Cleaner` whose `input_roles()` returns one role. A
"group" cleaner (e.g. `AddressCleaner`) is one whose `input_roles()` returns
many. Same contract, same execution method — no separate hierarchy.

```python
PRIMARY = "value"  # sentinel role key for the common single-column case


@checked
@dataclass
class Cleaner(ABC):
    inplace: bool = True
    split_components: bool = False

    _input_roles: tuple[ColumnRole, ...] = PrivateAttr()

    @model_validator(mode="after")
    def _infer_roles(self) -> Self:
        # Runs ONCE at construction. Inspects clean_row's signature.
        # Cached forever after -> zero cost at clean time.
        declared = self.input_roles()
        if declared:
            self._input_roles = declared
        else:
            sig_params = inspect.signature(self.clean_row).parameters
            self._input_roles = tuple(
                ColumnRole(
                    key=name, required=(param.default is inspect.Parameter.empty)
                )
                for name, param in sig_params.items()
            )
        return self

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]: ...

    @abstractmethod
    def clean_row(self, *args, **kwargs) -> CellValue | tuple[CellValue, ...] | None:
        """
        The ONLY cleaning entry point. Positional, ordered exactly by input_roles().
        No dict, no per-row unpacking overhead -- plain function call.
        """

    # override only when detector/name_hints needed beyond signature inference
    def input_roles(self) -> tuple[ColumnRole, ...]:
        return ()

    # override when this cleaner's output should be usable as another's context
    def provided_roles(self) -> tuple[str, ...]:
        return ()

    def get_data_type_confidence(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        return 0.0
```

**Immutability rule (unchanged):** all precomputation happens in
`model_validator(mode="after")`. `clean_row` does zero setup work, only
executes.

## 3. `ColumnRole` — shared descriptor for all input kinds

```python
@checked
@dataclass
class ColumnRole:
    key: str
    required: bool = True
    detector: "Cleaner | None" = None  # reuse an existing cleaner's confidence scoring
    name_hints: tuple[str, ...] = ()  # fallback keyword match
```

Same class powers the PRIMARY anchor column, optional context columns, and
group-cleaner input columns -- one mechanism, not three.

## 4. Author Experience

### Simple cleaner -- no boilerplate

```python
@checked
@dataclass
class EmailCleaner(Cleaner):
    def name(self) -> str:
        return "EmailCleaner"

    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]:
        return "str"

    def clean_row(self, value: str) -> str | None:
        # single required param "value" -> input_roles() auto-inferred as (PRIMARY, required=True)
        return self._parse_email(value)

    def get_data_type_confidence(self, df, cols) -> float:
        return 1.0 if "email" in cols[0].lower() else 0.0
```

### Cleaner with optional context -- still no `input_roles()` override needed

```python
@checked
@dataclass
class PhoneCleaner(Cleaner):
    def clean_row(self, value: str, country: str | None = None) -> str | None:
        # required role = "value" (no default), optional role = "country" (has default)
        # inferred automatically from signature
        ...

    def provided_roles(self) -> tuple[str, ...]:
        return ("phone",)
```

### Group cleaner -- explicit `input_roles()` when detector/name_hints needed

```python
@checked
@dataclass
class AddressCleaner(Cleaner):
    def input_roles(self) -> tuple[ColumnRole, ...]:
        return (
            ColumnRole(key="country", required=False, detector=CountryCleaner()),
            ColumnRole(key="state", required=False, name_hints=("state", "county")),
            ColumnRole(
                key="address_line_1",
                required=True,
                name_hints=("address_line1", "address1"),
            ),
            ColumnRole(
                key="address_line_2", required=False, name_hints=("address_line2",)
            ),
            ColumnRole(
                key="address_line_3", required=False, name_hints=("address_line3",)
            ),
            ColumnRole(key="postcode", required=False, detector=PostCodeCleaner()),
        )

    def provided_roles(self) -> tuple[str, ...]:
        return ("country", "state", "postcode", "address_line", "street", "house_no")

    def output_schema(self):
        return tuple((r, "str") for r in self.provided_roles())

    def clean_row(
        self, country, state, address_line_1, address_line_2, address_line_3, postcode
    ):
        # positional, ordered exactly per input_roles()
        ...
```

Validated once at construction: explicit `input_roles()` param count/order must
match `clean_row`'s signature -- mismatch fails loud immediately, not at
runtime.

## 5. Resolution Pipeline

| Phase | Component | Purpose |
|---|---|---|
| 0 | `Resolver` | Sort cleaners by required-role count (most-constrained first). For each, score unclaimed columns against each role: PRIMARY/detector roles via confidence scoring, name_hints roles via keyword match |
| 1 | `Resolver` | If all `required` roles matched above threshold -> claim those columns, compute overall confidence, remove from unclaimed pool. Explicit user `{col: cleaner}` mapping always wins, skips scoring |
| 2 | `EntityExtractor` + `DependencyResolver` | Build `role -> [candidate assignments]` map from `provided_roles()` (list, not single value -- see Section 7) |
| 3 | `DependencyResolver` | For each `context_requests()` (roles with `required=False`/`True` beyond PRIMARY), resolve candidates: 1 candidate -> use directly; >1 -> disambiguate via entity-token overlap |
| 4 | `DependencyResolver` | Build dependency graph from resolved producer -> consumer edges. Topologically sort into execution **waves**. Cycle -> `PipelineConfigError` |
| 5 | `Pipeline._apply` | Execute wave by wave; each wave's outputs become available as context for later waves; finalize by dropping raw/intermediate columns, keeping only final cleaned column names |

## 6. Entity/Namespace Disambiguation

Solves: `client_phone`/`client_country` vs `manager_phone`/`manager_country`.

```python
class EntityExtractor:
    def __init__(self, words_fn: Callable[[str], tuple[str, ...]]):
        self._words = (
            words_fn  # injected: reuses ColRenamer._get_words, no duplicate tokenizer
        )

    def extract(self, column: str, role: str) -> tuple[str, ...]:
        role_tokens = set(self._words(role))
        return tuple(t for t in self._words(column) if t.lower() not in role_tokens)
```

| Rule | Behavior |
|---|---|
| Exactly 1 producer for a role | Used directly, no entity matching needed |
| Multiple producers, role token IS a substring of each column name | Strip role token, compare entity overlap (e.g. `client_phone` -> `client`) |
| Multiple producers, role token NOT present in column names (aliases, e.g. `tel`/`fax` for role `phone`) | No signal to strip -- see Section 7 |
| Overlap tied or zero across all candidates | `required=False` -> skip context (degrade gracefully); `required=True` -> raise `PipelineConfigError` |
| User-supplied `context_overrides={"client_phone": {"country": "client_country"}}` | Always checked first, bypasses auto-matching entirely |

## 7. Same-Role Multiplicity -- Two Distinct Situations

**A. Multiple PRIMARY columns matching the same cleaner type (`phone`, `tel`,
`fax` all match `PhoneCleaner`):** Not a conflict. PRIMARY resolution runs
independently per column (Phase 0-1) -- each of `phone`, `tel`, `fax` gets its
own `ColumnAssignment` and its own output column (`phone_cleaned`,
`tel_cleaned`, `fax_cleaned`). No merging.

**B. Multiple *producers* of the same role, requested as context by another
cleaner:**

| Case | Column names share role token? | Resolvable? |
|---|---|---|
| `client_phone` / `manager_phone` producing role `phone` | Yes -- token `phone` present, entity = `client`/`manager` | Entity matching resolves it |
| `phone` / `tel` / `fax` all producing role `phone` | No -- `tel`/`fax` don't contain the word `phone` | No naming signal -- unresolved by default |

Design decision: aliases without namespace hints are
**intentionally unresolvable** -- not a gap to patch with smarter heuristics
later.

| Rule | Behavior |
|---|---|
| Multiple role producers, zero entity-overlap signal across all of them | Unresolved -- same as tied/zero-overlap case: skip if `required=False`, `PipelineConfigError` if `required=True` |
| User wants a specific one anyway | `context_overrides={"some_col": {"phone": "tel"}}` -- explicit escape hatch |
| Never silently pick "first match" | A silent wrong guess is worse than requiring one line of explicit config |

## 8. Value Objects

```python
@dataclass(frozen=True)
class Assignment:
    cleaner: Cleaner
    role_columns: Mapping[str, str]  # role.key -> actual raw column name
    confidence: float


@dataclass(frozen=True)
class ExecutionPlan:
    waves: tuple[tuple[Assignment, ...], ...]
```

Note: `ColumnAssignment`/`GroupAssignment` split from the earlier design
collapses into one `Assignment` type -- PRIMARY-only cleaners just have
`role_columns = {PRIMARY: col}`.

## 9. Pipeline API

```python
class Pipeline:
    def __init__(
        self,
        cleaners: Sequence[Cleaner] = (),
        column_cleaners: Mapping[str, Cleaner] | None = None,  # explicit overrides
        context_overrides: Mapping[str, Mapping[str, str]] | None = None,
        auto_detect: bool = True,
    ): ...

    def fit_transform(self, df: DataFrame | Any) -> DataFrame: ...
```

```python
# Explicit
pipeline = Pipeline(cleaners=[EmailCleaner(), PhoneCleaner(), AddressCleaner()])
cleaned_df = pipeline.fit_transform(df)

# One-liner sugar (table I/O)
dataclean.clean("prod.raw.some_table", dest="prod.prep.*")
```

## 10. Performance Notes

| Concern | Resolution |
|---|---|
| Per-row dict build/unpack (original concern) | Eliminated -- `clean_row` is positional, matches existing `DataWriter.expr` callable contract (`Callable[..., str]`) used via `*args` in `pandas.py`/`pyspark.py`. No engine changes needed. |
| Role -> column mapping cost | Computed once at pipeline-build time (`Assignment.role_columns`), reused unchanged for every row |
| Role inference cost | Runs once via `inspect.signature` at cleaner construction (`model_validator`), cached in `_input_roles` |

## 11. Error Handling

| Situation | Behavior |
|---|---|
| Single value fails to clean | Returns `None` (existing convention, unchanged) |
| Required role unmatched (PRIMARY or group role) | `PipelineConfigError` |
| Required context role unmatched/ambiguous | `PipelineConfigError` |
| Multiple role producers with no entity signal (Section 7B) | Unresolved -- skip if optional, error if required |
| Dependency cycle between cleaners | `PipelineConfigError` |
| No cleaner confident enough for a column (`auto_detect=True`) | Column left untouched, logged as warning |
| `input_roles()` override doesn't match `clean_row` signature | Fails at construction (`model_validator`), not at runtime |

## 12. Deferred to Rust Migration (post-1.0)

- Batch (vectorized) execution
- Arrow-native data crossing
- Rust-side `#[pyclass]` configs replacing Pydantic for built-ins
- Everything in `DESIGN_PLAN.md` Sections 2-6

## 13. Work Items for v1.0

- [ ] Unified `Cleaner` ABC (replaces `Cleaner`/`BaseCleaner`/`GroupCleaner`
      split)
- [ ] `ColumnRole`, `Assignment`, `ExecutionPlan` data classes
- [ ] Signature-based role inference (`_infer_roles` validator)
- [ ] `EntityExtractor` (reusing `ColRenamer._get_words`)
- [ ] `Resolver` (merged group+single claiming, most-constrained-first)
- [ ] `DependencyResolver` with entity disambiguation + unresolved-alias
      handling
- [ ] Topological sort into `ExecutionPlan.waves`, cycle detection
- [ ] `Pipeline` class (`fit_transform`, `column_cleaners`, `context_overrides`)
- [ ] `Catalog` ABC + platform auto-detection registry
- [ ] `dataclean.clean(str, dest=...)` sugar function
- [ ] Retrofit `PhoneCleaner`/`CountryCleaner`/etc. to unified `Cleaner`
- [ ] `PipelineConfigError` + exception hierarchy
