"""Data I/O helpers.

Thin wrappers around pyreadstat and pandas parquet so notebooks stay short.
Nothing here does cohort-specific work — that lives in the project's
preprocess module.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pyreadstat


def read_sav(path: str | Path) -> tuple[pd.DataFrame, Any]:
    """Read an SPSS `.sav` file, returning `(df, meta)`.

    `meta` is a pyreadstat metadata object exposing `.value_labels`,
    `.variable_value_labels`, `.column_labels` etc.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    return pyreadstat.read_sav(str(path))


def apply_value_labels(df: pd.DataFrame, meta: Any) -> pd.DataFrame:
    """Return a copy of `df` with numeric SPSS codes replaced by their labels.

    Silently returns `df` unchanged if the metadata carries no labels.
    """
    if meta is None or not getattr(meta, "value_labels", None):
        return df

    result = df.copy()
    value_sets = meta.value_labels
    variable_map = getattr(meta, "variable_value_labels", {}) or {}

    for column, label_set in variable_map.items():
        if column not in result.columns:
            continue
        mapping = label_set if isinstance(label_set, dict) else value_sets.get(label_set, {})
        if mapping:
            result[column] = result[column].replace(mapping)
    return result


def read_parquet(path: str | Path) -> pd.DataFrame:
    """Read a parquet file with the pyarrow engine (default in pandas ≥ 2)."""
    return pd.read_parquet(Path(path), engine="pyarrow")


def write_parquet(df: pd.DataFrame, path: str | Path) -> None:
    """Write `df` to parquet, creating parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
