"""dataclean - Data cleaning library with automatic column detection."""

from dataclean.pipeline import Pipeline
from dataclean.pipeline.catalog import Catalog, DefaultCatalog
from dataclean.pipeline.exceptions import (
    DatacleanError,
    PipelineConfigError,
)

__version__ = "1.0.0"

__all__ = [
    "Pipeline",
    "Catalog",
    "DefaultCatalog",
    "DatacleanError",
    "PipelineConfigError",
    "clean",
]


def clean(
    df,
    auto_detect: bool = True,
    catalog: Catalog | None = None,
):
    """
    Clean a dataframe with automatic cleaner detection.

    Args:
        df: DataFrame to clean (pandas, pyspark, or DataFrame-compatible).
        auto_detect: If True, auto-detect cleaners for columns.
        catalog: Catalog to use for cleaner registration (defaults to DefaultCatalog).

    Returns:
        Cleaned DataFrame.

    Example:
        >>> import pandas as pd
        >>> from dataclean import clean
        >>> df = pd.DataFrame({"email": ["john.doe@example.com"]})
        >>> cleaned = clean(df)
    """
    if catalog is None:
        catalog = DefaultCatalog()

    pipeline = Pipeline(
        cleaners=catalog.get_cleaners(),
        auto_detect=auto_detect,
    )
    return pipeline.fit_transform(df)
