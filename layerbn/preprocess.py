"""Generic preprocessing transforms.

Cohort-agnostic dataframe operations used by every project:
`coalesce`, date parsing, string cleanup, label translation via a
user-supplied mapping, and imputation.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

import pandas as pd
from sklearn.experimental import enable_iterative_imputer  # noqa: F401  (side-effect import)
from sklearn.impute import IterativeImputer


def coalesce(df: pd.DataFrame, cols: Sequence[str], target: str) -> None:
    """Mimic dplyr::coalesce: first non-null across `cols` written to `target`.

    Mutates `df` in place. Columns absent from `df` are skipped silently
    so callers can pass a superset without a KeyError.
    """
    series = None
    for col in cols:
        if col not in df:
            continue
        series = df[col] if series is None else series.fillna(df[col])
    if series is not None:
        df[target] = series


def to_datetime(df: pd.DataFrame, columns: Iterable[str]) -> None:
    """Parse the given columns to datetime, coercing errors to NaT."""
    for col in columns:
        if col in df:
            df[col] = pd.to_datetime(df[col], errors="coerce")


def normalise_string_categories(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from every object-typed column. Mutates and returns."""
    for col in df.select_dtypes(include="object"):
        df[col] = df[col].astype(str).str.strip()
    return df


def translate_labels(
    df: pd.DataFrame,
    label_map: Mapping[str, Mapping[str, str]],
) -> pd.DataFrame:
    """Apply per-column value translations from `label_map`.

    `label_map` is `{column_name: {source_value: target_value, ...}}`.
    Matching is case-insensitive on the source value. Columns become
    categorical after translation. Mutates and returns `df`.
    """
    for column, mapping in label_map.items():
        if column not in df:
            continue
        series = df[column].astype(str)
        lower = series.str.strip().str.casefold()
        normalized_mapping = {k.casefold(): v for k, v in mapping.items()}
        mapped = lower.map(normalized_mapping)
        df[column] = series.where(mapped.isna(), mapped).astype("category")
    return df


def impute_dataframe(df: pd.DataFrame, seed: int = 1234) -> pd.DataFrame:
    """Impute missing values.

    Numeric columns: IterativeImputer (multivariate, sklearn).
    Categorical/string columns: filled with the modal value; a new
    category is added if the mode isn't already among the existing ones.

    Column order is preserved.
    """
    numeric = df.select_dtypes(include=["number"]).copy()
    other = df.select_dtypes(exclude=["number"]).copy()

    if not numeric.empty:
        imputer = IterativeImputer(random_state=seed, sample_posterior=False)
        numeric = pd.DataFrame(
            imputer.fit_transform(numeric),
            columns=numeric.columns,
            index=df.index,
        )

    for col in other.columns:
        series = other[col]
        if not series.isnull().any():
            continue
        modes = series.mode(dropna=True)
        if isinstance(series.dtype, pd.CategoricalDtype):
            fill = modes.iloc[0] if not modes.empty else series.cat.categories[0]
            if fill not in series.cat.categories:
                series = series.cat.add_categories([fill])
        else:
            fill = modes.iloc[0] if not modes.empty else ""
        other[col] = series.fillna(fill)

    combined = pd.concat([numeric, other], axis=1)
    return combined[df.columns]


def contains_any(series: pd.Series | None, patterns: Sequence[str]) -> pd.Series:
    """Case-insensitive regex OR-search across free-text fields.

    Returns a boolean Series of the same length as `series` (or an all-False
    Series if `series` is None), so results can be combined with `|`/`&`.
    """
    if series is None:
        return pd.Series(False)
    pattern = "|".join(patterns)
    return series.fillna("").astype(str).str.contains(pattern, case=False, regex=True)
