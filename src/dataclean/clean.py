from .pipeline import (
    Pipeline,
    PipelineCatalog,
    PipelineDefaultCatalog,
)


def clean(
    df,
    auto_detect: bool = True,
    catalog: PipelineCatalog | None = None,
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
        catalog = PipelineDefaultCatalog()

    pipeline = Pipeline(
        cleaners=catalog.get_cleaners(),
        auto_detect=auto_detect,
    )
    return pipeline.fit_transform(df)
