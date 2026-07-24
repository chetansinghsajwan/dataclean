# dataclean — Architecture & Design Plan

Status: Approved direction. Rust core + Python API redesign.

## 1. Goals

- User-friendly, beginner-friendly, unambiguous Python API
- Object-oriented design throughout
- High performance, no repeated/duplicated logic

## 2. High-Level Architecture

| Layer | Decision |
|---|---|
| Repo structure | Single crate + single Python package (monorepo) |
| Core logic | Rust (`dataclean_core`), exposed via PyO3 |
| Build tool | `maturin` (native PyO3 tool, cross-platform wheels, integrates with `uv`) |
| Data crossing Rust↔Python boundary | Apache Arrow `RecordBatch` end-to-end (zero-copy via Arrow C Data Interface) |
| Cleaner trait | Batch-oriented `clean_column`, with default fallback to per-value `clean_value` |
| Custom cleaners | Two paths — Python (easy, subclass) and Rust (advanced, implement trait) |
| Config schema | Rust `#[pyclass]` structs for built-in cleaner configs (no Pydantic, single source of truth); Pydantic retained only for orchestration-level config and Python-path custom cleaners |
| Error handling | `None` for uncleanable *values* (expected, not exceptional); typed `DatacleanError` hierarchy raised as Python exceptions for real failures (bad config, schema mismatch, engine errors) |
| PySpark engine | Rust core invoked inside existing `pandas_udf` (executor-side Python + Arrow) — no JNI, no gRPC service |
| Top-level API | sklearn-style `Pipeline` class as the OOP core |
| Table I/O | Pluggable `Catalog` registry (auto-detects platform via env vars, override via `DATACLEAN_PLATFORM`) |
| Convenience API | `dataclean.clean(str, dest=...)` — thin sugar over `Catalog.read → Pipeline.fit_transform → Catalog.write` |

## 3. Rejected Alternatives (and why)

| Option | Rejected because |
|---|---|
| gRPC service for Rust core | Adds network hop + process management overhead; PyO3 in-process is sufficient once we route through `pandas_udf` for Spark |
| JNI bridge (Rust → JVM UDF) | Very high effort/risk — need to marshal Arrow across JNI, ship native libs per OS/arch to every executor |
| Rust core owns table I/O only via Spark Connect | Unnecessary complexity; `pandas_udf` already gives Arrow-native executor-side Python |
| Pydantic for built-in cleaner configs | Would duplicate validation logic (Python + Rust), violates "don't repeat code" goal |
| Per-value-only cleaner trait | Pays FFI/call overhead per row; can't vectorize in Rust |

## 4. Rust Crate Layout

```
dataclean_core/
├── Cargo.toml
├── pyproject.toml          # maturin config
└── src/
    ├── lib.rs               # #[pymodule] entry point
    ├── error.rs             # DatacleanError enum -> PyErr
    ├── cleaner/
    │   ├── mod.rs            # Cleaner trait + CleanedValue enum
    │   ├── registry.rs       # built-in registry, confidence-based auto-select
    │   ├── email.rs
    │   ├── phone.rs
    │   ├── numeric.rs
    │   ├── text.rs
    │   ├── datetime.rs
    │   ├── uuid.rs
    │   ├── country.rs
    │   ├── gender.rs
    │   └── bool_.rs
    ├── pipeline.rs           # Pipeline: orchestrates cleaners over a RecordBatch
    └── python/
        ├── mod.rs             # pyclass registrations
        ├── cleaners.rs        # #[pyclass] config structs
        └── pipeline.rs        # #[pyclass] Pipeline wrapper
```

### Core trait

```rust
pub trait Cleaner: Send + Sync {
    fn name(&self) -> &'static str;
    fn output_schema(&self) -> DataType;                 // arrow DataType
    fn clean_value(&self, v: &str) -> Option<CleanedValue>;

    // Default: maps clean_value over the array.
    // Built-ins override for SIMD / vectorized speed.
    fn clean_column(&self, input: &ArrayRef) -> Result<ArrayRef, DatacleanError> {
        // build via arrow ArrayBuilder, calling clean_value per element
    }

    fn confidence(&self, col_name: &str, sample: &ArrayRef) -> f32;
}

pub enum CleanedValue {
    Str(String),
    Int(i64),
    Float(f64),
    Bool(bool),
}
```

### Key implementation notes

| Concern | Approach |
|---|---|
| Extensibility | `Box<dyn Cleaner>` trait objects in registry — same trait for built-in and custom cleaners |
| Parallelism | `rayon` — across columns (independent) and row-chunks within `clean_column` for built-ins |
| Arrow transfer | Arrow C Data Interface (`arrow::ffi`) for zero-copy handoff to/from `pyarrow` |
| Config → Cleaner | `#[pyclass]` config struct holds plain fields; `.build()` constructs the concrete `Cleaner` impl once at creation (matches immutable/frozen, validate-once principle from current `AGENTS.md`) |
| Error mapping | `DatacleanError` (via `thiserror`) → `PyErr` via `impl From<DatacleanError> for PyErr` |
| Registry selection | Confidence-scoring loop (ports current `get_cleaner()` logic), iterates `Vec<Box<dyn Cleaner>>` |

## 5. Python API Surface

### Power-user / explicit (OOP core)
```python
from dataclean import Pipeline
from dataclean.cleaners import EmailCleaner, PhoneCleaner

pipeline = Pipeline(
    cleaners=[EmailCleaner(), PhoneCleaner(default_regions=("IN",))],  # explicit, optional per column
    auto_detect=True,  # default True — fills gaps for columns with no explicit cleaner
)
cleaned_df = pipeline.fit_transform(df)
```
- Explicit `cleaners` always wins per-column; `auto_detect` fills the rest — no ambiguity.

### Beginner / one-liner (sugar over the above)
```python
import dataclean
dataclean.clean("prod.raw.some_table", dest="prod.prep.*")
# -> auto-detects platform, reads "some_table",
#    runs Pipeline(auto_detect=True), writes "prod.prep.some_table"
#    (* in dest is replaced with the source table name)
```

## 6. Catalog / Platform Auto-Detection

```python
class Catalog(ABC):
    @staticmethod
    @abstractmethod
    def detect() -> bool: ...     # checks env vars / active session
    @abstractmethod
    def read_table(self, ref: str) -> DataFrame: ...
    @abstractmethod
    def write_table(self, ref: str, df: DataFrame) -> None: ...
```

| Platform | Detection signal |
|---|---|
| Explicit override | `DATACLEAN_PLATFORM` env var — always wins, no guessing |
| Databricks (Unity Catalog) | `DATABRICKS_RUNTIME_VERSION` env var present |
| Local/standalone Spark | Active `SparkSession` exists, or `SPARK_HOME` set |
| Snowflake | `SNOWFLAKE_ACCOUNT` / connector env vars present |
| BigQuery | `GOOGLE_CLOUD_PROJECT` + `GOOGLE_APPLICATION_CREDENTIALS` present |
| Fallback | Local file / Pandas, if nothing detected |

- Registry checked in order; first `detect() == True` wins — same plugin pattern as `DataFrame.supports()` today.
- New `Catalog` implementations are pluggable, same as `DataFrame` engines.

## 7. Open Items for Later Sessions

- [ ] Migration plan from current pure-Python implementation
- [ ] CI/CD for multi-platform wheel builds (maturin + GitHub Actions matrix)
- [ ] Testing strategy split (Rust unit tests vs Python integration tests)
- [ ] Full spec for `Pipeline.fit` vs `.transform` semantics (schema caching for train/serve consistency)
- [ ] Versioning/release strategy for `dataclean_core` vs Python package
