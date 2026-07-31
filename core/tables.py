"""Grouped descriptive tables ("Table 1" style).

`build_grouped_table` takes a spec describing which rows to render and
returns a wide DataFrame with one column per group. The spec keeps the
cohort-specific column names outside this module — projects supply
their own list.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

import pandas as pd


# ---------------------------------------------------------------------------
# formatters
# ---------------------------------------------------------------------------

def _normalize_label(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        if not value.strip():
            return None
        return value.strip().casefold()
    if isinstance(value, (float, int)) and pd.isna(value):
        return None
    return str(value).strip().casefold()


def format_median_iqr(series: pd.Series | None) -> str:
    """`"median [q25, q75]"` with two decimals, or `"NA"` if empty."""
    if series is None:
        return "NA"
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return "NA"
    q1, med, q3 = numeric.quantile(0.25), numeric.median(), numeric.quantile(0.75)
    return f"{med:.2f} [{q1:.2f}, {q3:.2f}]"


def format_mean_sd(series: pd.Series | None) -> str:
    """`"mean (sd)"` with two decimals, or `"NA"` if empty."""
    if series is None:
        return "NA"
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return "NA"
    return f"{numeric.mean():.2f} ({numeric.std():.2f})"


def format_count_pct(series: pd.Series | None, targets: Sequence[str]) -> str:
    """`"n (pct)"` of values in `series` matching any label in `targets`."""
    if series is None:
        return "NA"
    normalized = pd.Series(series).dropna().map(_normalize_label).dropna()
    if normalized.empty:
        return "NA"
    target_norms = {_normalize_label(v) for v in targets if v is not None}
    target_norms.discard(None)
    if not target_norms:
        return "NA"
    count = normalized.isin(target_norms).sum()
    pct = (count / len(normalized)) * 100
    return f"{int(count)} ({pct:.1f})"


# ---------------------------------------------------------------------------
# row specs
# ---------------------------------------------------------------------------

@dataclass
class Row:
    """One row in a grouped table.

    Either `formatter` (called with a group's dataframe) or the pair
    (`column`, `category_targets`) must be provided. Use `submetric` when
    a metric fans out into multiple rows (e.g. category breakdowns).
    """
    metric: str
    submetric: str = ""
    formatter: Callable[[pd.DataFrame], str] | None = None
    column: str | None = None
    category_targets: Sequence[str] | None = None


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def build_grouped_table(
    df: pd.DataFrame,
    *,
    group_col: str,
    group_order: Sequence[str] | None = None,
    rows: Sequence[Row],
    include_overall: bool = True,
) -> pd.DataFrame:
    """Return a wide DataFrame with one column per group.

    Groups appear in `group_order` first (those actually present in the
    data), followed by any additional group values in their natural
    order. When `include_overall=True`, a leading "Overall" column
    aggregates all rows.

    Missing columns / missing groups degrade to `"NA"` rather than
    raising — table generation should not block the run.
    """
    groups: list[tuple[str, pd.DataFrame]] = []
    if include_overall:
        groups.append(("Overall", df))

    if group_col in df:
        present = df[group_col].dropna().unique()
        added: set[Any] = set()
        for name in group_order or ():
            if name in present:
                groups.append((str(name), df[df[group_col] == name]))
                added.add(name)
        for value in present:
            if value in added:
                continue
            groups.append((str(value), df[df[group_col] == value]))
            added.add(value)

    records: list[dict[str, str]] = []
    for row in rows:
        entry: dict[str, str] = {"Metric": row.metric, "Submetric": row.submetric}
        for group_name, group_df in groups:
            entry[group_name] = _render(row, group_df)
        records.append(entry)

    if not records:
        return pd.DataFrame()

    columns = ["Metric", "Submetric"] + [name for name, _ in groups]
    return pd.DataFrame(records).loc[:, columns]


def _render(row: Row, group_df: pd.DataFrame) -> str:
    if row.formatter is not None:
        return row.formatter(group_df)
    if row.column is None:
        return "NA"
    series = group_df.get(row.column)
    if row.category_targets is not None:
        return format_count_pct(series, row.category_targets)
    return format_median_iqr(series)


def category_rows(
    metric: str,
    column: str,
    categories: Sequence[tuple[str, Sequence[str]]],
) -> list[Row]:
    """Convenience: build one `Row` per category label.

    `categories` is a sequence of `(display_label, [target_values, ...])`
    tuples, matched against the column via case-insensitive equality.
    """
    return [
        Row(metric=metric, submetric=label, column=column, category_targets=targets)
        for label, targets in categories
    ]
