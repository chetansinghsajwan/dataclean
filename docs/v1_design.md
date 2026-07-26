# dataclean v1.0 — Pure Python Design

Scope: v1.0 ships as pure Python (current architecture, refined). Rust core
migration begins after 1.0 — see `DESIGN_PLAN.md`.

## 1. Goals

- User-friendly, unambiguous, beginner-friendly API
- Object-oriented, no duplicated logic
- Cleaners are immutable, constructed once, precompute at construction
- Automatic column → cleaner assignment with graceful degradation, never silent
  wrong guesses

## 2. Class Hierarchy

```text
Cleaner (ABC, frozen)
├── BaseCleaner              # single primary column + optional context roles
└── GroupCleaner             # multiple input roles -> multiple output columns
```

| Class | Consumes | Produces | Example |
|---|---|---|---|
| `BaseCleaner` | 1 primary column (+ optional context) | 1 or split-component columns | `PhoneCleaner`, `CountryCleaner`, `EmailCleaner` |
| `GroupCleaner` | multiple columns, matched via roles | multiple named output columns | `AddressCleaner` |

## 3. Core Contracts

```python
class Cleaner(StrictBaseModel, ABC, frozen=True):
    def provided_roles(self) -> tuple[str, ...]:
        """Semantic role(s) this cleaner's output represents. e.g. ("country",)"""
        return ()


class ContextRequest(StrictBaseModel, frozen=True):
    role: str
    required: bool = False


class BaseCleaner(Cleaner, ABC, frozen=True):
    inplace: bool = True
    split_components: bool = False

    def name(self) -> str: ...
    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]: ...
    def clean_value(
        self, value: str, context: "CleanContext | None" = None
    ) -> CellValue | None: ...
    def get_data_type_confidence(
        self, df: DataFrame, cols: tuple[str, ...]
    ) -> float: ...
    def context_requests(self) -> tuple[ContextRequest, ...]:
        return ()


class ColumnRole(StrictBaseModel, frozen=True):
    key: str
    required: bool = True
    detector: BaseCleaner | None = (
        None  # reuse an existing cleaner's confidence scoring
    )
    name_hints: tuple[str, ...] = ()  # fallback keyword match


class GroupCleaner(Cleaner, ABC, frozen=True):
    def name(self) -> str: ...
    def output_schema(self) -> tuple[tuple[str, DataType], ...]: ...
    def input_roles(self) -> tuple[ColumnRole, ...]: ...
    def clean_row(
        self, values: Mapping[str, CellValue | None]
    ) -> tuple[CellValue | None, ...] | None: ...
    def group_confidence(self, role_scores: Mapping[str, float]) -> float: ...
```

**Immutability rule (unchanged from today):** all precomputation — regex
compilation, pipeline construction, lookup tables — happens in
`model_validator(mode="after")`. `clean_value` / `clean_row` do zero setup work,
only execute.

## 4. Value Objects

```python
@dataclass(frozen=True)
class ColumnAssignment:
    column: str
    cleaner: BaseCleaner
    confidence: float


@dataclass(frozen=True)
class GroupAssignment:
    cleaner: GroupCleaner
    role_columns: Mapping[str, str]  # role.key -> actual raw column name
    confidence: float


@dataclass(frozen=True)
class CleanContext:
    values: Mapping[str, CellValue]  # role -> value, for the current row


@dataclass(frozen=True)
class ExecutionPlan:
    waves: tuple[tuple[ColumnAssignment | GroupAssignment, ...], ...]
```

## 5. Resolution Pipeline — 6 Phases

| Phase | Component | Purpose |
|---|---|---|
| 0 | `GroupCleanerResolver` | Score every unclaimed column against each registered `GroupCleaner`'s roles (via `detector` confidence or `name_hints`) |
| 1 | `GroupCleanerResolver` | If all `required` roles matched above threshold → claim those columns, compute `group_confidence`, remove from unclaimed pool |
| 2 | `CleanerResolver` | For remaining unclaimed columns, score every `BaseCleaner` via `get_data_type_confidence`; highest wins, short-circuit at 1.0. Explicit user `{col: cleaner}` mapping always wins, skips scoring |
| 3 | `EntityExtractor` + `DependencyResolver` | Build role-producer map from `provided_roles()`. For each `context_requests()`, find candidate producer(s) of that role |
| 4 | `DependencyResolver` | If >1 candidate producer for a role, disambiguate via entity-token overlap (see §6). Build dependency graph, topologically sort into execution **waves**. Cycle → raise `PipelineConfigError` |
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
| Multiple producers | Pick producer with highest entity-token overlap with consumer |
| Overlap tied or zero across all candidates | `required=False` → skip context (degrade gracefully); `required=True` → raise `PipelineConfigError` |
| User-supplied `context_overrides={"client_phone": {"country": "client_country"}}` | Always checked first, bypasses auto-matching entirely |

## 7. Pipeline API

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
pipeline = Pipeline(
    cleaners=[EmailCleaner(), PhoneCleaner(default_regions=("IN",)), AddressCleaner()]
)
cleaned_df = pipeline.fit_transform(df)

# One-liner sugar (table I/O, from earlier design)
dataclean.clean("prod.raw.some_table", dest="prod.prep.*")
```

## 8. Error Handling

| Situation | Behavior |
|---|---|
| Single value fails to clean | Returns `None` (existing convention, unchanged) |
| Required group role unmatched | `PipelineConfigError` |
| Required context role unmatched/ambiguous | `PipelineConfigError` |
| Dependency cycle between cleaners | `PipelineConfigError` |
| No cleaner confident enough for a column (`auto_detect=True`) | Column left untouched, logged as warning (existing behavior) |

## 9. Worked End-to-End Example

Raw columns: `client_phone`, `client_country`, `manager_phone`,
`manager_country`, `county`, `country`, `address_line1`, `address_line2`,
`address_line3`

| Wave | Assignment | Reads | Produces |
|---|---|---|---|
| 0 | `AddressCleaner` (group) | `county, country, address_line1/2/3` | `country, state, postcode, address_line, street, house_no` |
| 0 | `CountryCleaner` | `client_country` | `client_country` (cleaned) |
| 0 | `CountryCleaner` | `manager_country` | `manager_country` (cleaned) |
| 1 | `PhoneCleaner` | `client_phone` + context `client_country` (entity match) | `client_phone` (cleaned) |
| 1 | `PhoneCleaner` | `manager_phone` + context `manager_country` (entity match) | `manager_phone` (cleaned) |

## 10. Deferred to Rust Migration (post-1.0)

- Batch (`clean_column`) vectorized execution
- Arrow-native data crossing
- Rust-side `#[pyclass]` configs replacing Pydantic for built-ins
- Everything in `DESIGN_PLAN.md` §2–§6

## 11. New Work Items for v1.0

- [ ] `Cleaner` ABC + refactor `BaseCleaner` to inherit from it, add
      `provided_roles()`
- [ ] `ContextRequest`, `CleanContext`, `ColumnRole` data classes
- [ ] `GroupCleaner` ABC + first implementation: `AddressCleaner`
- [ ] `EntityExtractor` (reusing `ColRenamer._get_words`)
- [ ] `GroupCleanerResolver`, `CleanerResolver`, `DependencyResolver`
- [ ] `ExecutionPlan` + topological sort with cycle detection
- [ ] `Pipeline` class (`fit_transform`, `column_cleaners`, `context_overrides`)
- [ ] `Catalog` ABC + platform auto-detection registry
- [ ] `dataclean.clean(str, dest=...)` sugar function
- [ ] Retrofit `PhoneCleaner`/`CountryCleaner` with `provided_roles()` /
      `context_requests()`
- [ ] `PipelineConfigError` + exception hierarchy
