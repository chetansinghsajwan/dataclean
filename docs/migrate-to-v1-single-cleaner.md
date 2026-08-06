# Migration: V1 Python Design -> Dataclean Design V1 (Single Cleaner)

Purpose: step-by-step diff/migration guide from `V1_PYTHON_DESIGN.md` (original
`Cleaner`/`BaseCleaner`/`GroupCleaner` 3-class hierarchy) to
`DATACLEAN_DESIGN_V1.md` (unified single `Cleaner` class). Use this if
implementation of the original design has already started and needs to be
refactored, or as a reference for why the change was made.

## 1. Why the change

| Problem with original design | Fixed by unified design |
|---|---|
| `BaseCleaner` and `GroupCleaner` duplicated most of the contract (`name`, `output_schema`, confidence-adjacent logic) just to support 1-column vs N-column cases | One `Cleaner` class; N-column-ness is just `input_roles()` returning more than one role |
| `clean_value(value, context)` vs `clean_row(values: Mapping)` were two different signatures for conceptually the same operation | Single `clean_row(*args)` for all cleaners |
| `CleanContext` dict built and unpacked per row, per column -> real overhead at scale (1000 rows x 10 cols) | Positional args -- plain function call, matches existing `DataWriter.expr` contract already used in `pandas.py`/`pyspark.py` |
| `ColumnAssignment` and `GroupAssignment` were separate value objects | Single `Assignment` type, `role_columns` mapping covers both cases |
| Resolver had a hard "group phase" vs "single phase" split | One resolver loop, sorted by required-role count |

## 2. Class hierarchy diff

**Before:**

```text
Cleaner (ABC, frozen)
├── BaseCleaner       # clean_value(value, context)
└── GroupCleaner       # clean_row(values: Mapping)
```

**After:**

```text
Cleaner (ABC, frozen)   # only class -- clean_row(*args), input_roles() length = 1 or many
```

Action items:

- [ ] Delete `BaseCleaner` and `GroupCleaner` classes entirely
- [ ] All existing cleaner subclasses (`EmailCleaner`, `PhoneCleaner`,
      `TextCleaner`, `NumericCleaner`, `BoolCleaner`, `GenderCleaner`,
      `DateTimeCleaner`, `CountryCleaner`, `UuidCleaner`) now inherit directly
      from `Cleaner`

## 3. Method signature diff

| Original (`BaseCleaner`) | New (`Cleaner`) | Migration note |
|---|---|---|
| `clean_value(self, value: str, context: CleanContext \| None = None) -> CellValue \| None` | `clean_row(self, value: str, **context_kwargs) -> CellValue \| None` | Rename method. Replace `context.get(SomeCleanerType)` lookups with plain keyword params, e.g. `country: str \| None = None` |
| `context_requests() -> tuple[ContextRequest, ...]` | Not overridden for simple cases -- inferred from `clean_row` signature | Only override `input_roles()` explicitly if you need `detector=`/`name_hints=` beyond what a plain param name implies |

| Original (`GroupCleaner`) | New (`Cleaner`) | Migration note |
|---|---|---|
| `clean_row(self, values: Mapping[str, CellValue \| None]) -> Mapping[str, CellValue] \| None` | `clean_row(self, country, state, address_line_1, ...) -> tuple[CellValue, ...] \| None` | Change from dict param + dict return, to positional params + positional/tuple return, ordered exactly per `input_roles()` |
| `input_roles() -> tuple[ColumnRole, ...]` | Same, unchanged | `ColumnRole` class itself is unchanged -- no migration needed here |

## 4. Example: `PhoneCleaner` before/after

**Before:**

```python
class PhoneCleaner(BaseCleaner, frozen=True):
    def context_requests(self) -> tuple[ContextRequest, ...]:
        return (ContextRequest(role="country"),)

    def clean_value(self, value: str, context: CleanContext | None = None) -> str | None:
        country = context.get("country") if context else None
        ...
```

**After:**

```python
class PhoneCleaner(Cleaner, frozen=True):
    def clean_row(self, value: str, country: str | None = None) -> str | None:
        # required role "value" + optional role "country" auto-inferred from signature
        ...

    def provided_roles(self) -> tuple[str, ...]:
        return ("phone",)
```

No `input_roles()` override needed -- deleted entirely for this cleaner.

## 5. Example: `AddressCleaner` before/after

**Before:**

```python
class AddressCleaner(GroupCleaner, frozen=True):
    def input_roles(self) -> tuple[ColumnRole, ...]:
        return (...)  # unchanged, see below

    def clean_row(self, values: Mapping[str, str | None]) -> tuple[str | None, ...] | None:
        country = values["country"]
        address_1 = values["address_line_1"]
        ...
```

**After:**

```python
class AddressCleaner(Cleaner, frozen=True):
    def input_roles(self) -> tuple[ColumnRole, ...]:
        return (...)  # UNCHANGED -- ColumnRole definitions carry over as-is

    def clean_row(self, country, state, address_line_1, address_line_2, address_line_3, postcode):
        # same params, now positional instead of dict lookups
        ...
```

`input_roles()` body requires **no changes** -- only the base class and
`clean_row` signature change.

## 6. Value objects diff

| Original | New | Action |
|---|---|---|
| `ColumnAssignment` (single) | `Assignment` | Rename, merge fields: `role_columns: Mapping[str, str]` replaces bare `column: str` |
| `GroupAssignment` | `Assignment` | Same type as above now -- delete `GroupAssignment` entirely |
| `CleanContext` | *(removed)* | No longer needed -- context values are passed as plain kwargs |
| `ContextRequest` | *(removed, folded into `ColumnRole`)* | Any standalone `ContextRequest` usage becomes a `ColumnRole` entry, or is auto-inferred and not written at all |
| `ExecutionPlan` | `ExecutionPlan` | Unchanged shape (`waves: tuple[tuple[Assignment, ...], ...]`) |

## 7. Resolver diff

| Original phase | New phase | Change |
|---|---|---|
| Phase 0-1: `GroupCleanerResolver` (groups only) | Phase 0-1: `Resolver` (all cleaners) | Merge into one resolver; sort candidates by required-role count (most-constrained first) instead of a hard group-vs-single split |
| Phase 2: `CleanerResolver` (single only, runs after groups) | *(merged above)* | No longer a separate pass -- PRIMARY-role cleaners and multi-role cleaners go through the same loop |
| Phase 3: `EntityExtractor` + `DependencyResolver` | Phase 2-3: same, unchanged logic | `EntityExtractor` reused as-is. **New**: explicitly handle the case where role producers share no naming token at all (aliases like `tel`/`fax` for role `phone`) -- treat as unresolved rather than guessing (see `DATACLEAN_DESIGN_V1.md` Section 7) |
| Phase 4: `DependencyResolver` topo sort | Phase 4: same | Unchanged |
| Phase 5: `Pipeline._apply` | Phase 5: same | Unchanged, still wave-by-wave materialization |

## 8. Checklist — implementation not yet started

If you haven't written any code against the original design yet, skip the
diff-reading above and just implement directly from `DATACLEAN_DESIGN_V1.md`
Section 13's work-item list -- this migration doc is only needed if refactoring
existing code.

## 9. Checklist — implementation already in progress

- [ ] Delete `BaseCleaner`, `GroupCleaner`, `ContextRequest`, `CleanContext`,
      `GroupAssignment`
- [ ] Add unified `Cleaner` with `_infer_roles` validator (signature inspection)
- [ ] Convert every cleaner's `clean_value`/`clean_row` to the new positional
      `clean_row`
- [ ] Merge `GroupCleanerResolver` + `CleanerResolver` into single `Resolver`
- [ ] Rename `ColumnAssignment` -> `Assignment`, update all references
- [ ] Update `Pipeline._apply` to pass positional args instead of building
      `CleanContext`
- [ ] Add explicit unresolved-alias handling in `DependencyResolver` (Section 7B
      logic)
- [ ] Re-run/update unit tests for any cleaner whose `clean_value` signature
      changed
