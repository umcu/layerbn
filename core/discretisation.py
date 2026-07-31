"""Discretisation helpers.

Thin conveniences around pyAgrum's `DiscreteTypeProcessor` plus utilities
for reading its interval labels back out (needed by any sensitivity
analysis that resolves numeric evidence to a discrete bin).
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd


def make_type_processor(
    *,
    method: str = "quantile",
    n_bins: int = 4,
    threshold: int = 10,
) -> Any:
    """Build a pyAgrum `DiscreteTypeProcessor` with sensible defaults.

    `method` and `n_bins` are only applied to numeric columns with more
    than `threshold` unique values; below that, the column is treated as
    already-discrete and used verbatim.
    """
    from pyagrum.lib.discreteTypeProcessor import DiscreteTypeProcessor
    return DiscreteTypeProcessor(
        defaultDiscretizationMethod=method,
        defaultNumberOfBins=n_bins,
        discretizationThreshold=threshold,
    )


_INTERVAL_RE = re.compile(r"^[\[\(]\s*([-+0-9.eE]+)\s*;\s*([-+0-9.eE]+)\s*[\[\]\)]$")


def format_bin_label(label: str, decimals: int = 1) -> str:
    """Round the numeric endpoints of an interval label like `(2.71828;3.14159[`.

    Non-interval labels are returned unchanged.
    """
    match = _INTERVAL_RE.match(label.strip())
    if not match:
        return label
    lower = round(float(match.group(1)), decimals)
    upper = round(float(match.group(2)), decimals)
    return f"({lower};{upper}["


def state_for_value(labels: list[str], value: Any) -> str | None:
    """Resolve a raw `value` to one of the discretised `labels`.

    An exact string match wins. Otherwise, if the labels look like
    intervals ('(lo;hi[' or '[lo;hi[') and `value` is numeric, the bin
    containing it is returned (clamped to the extreme bins on either
    end). Returns `None` if unresolvable.
    """
    if str(value) in labels:
        return str(value)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    bins: list[tuple[float, float, str]] = []
    for lab in labels:
        match = _INTERVAL_RE.match(lab)
        if not match:
            return None  # not an interval-discretised variable at all
        bins.append((float(match.group(1)), float(match.group(2)), lab))
    if not bins:
        return None

    bins.sort()
    if numeric <= bins[0][0]:
        return bins[0][2]
    if numeric >= bins[-1][1]:
        return bins[-1][2]
    for lo, hi, lab in bins:
        if lo <= numeric < hi:
            return lab
    return bins[-1][2]


def describe_template(template: Any, decimals: int = 1) -> pd.DataFrame:
    """Return one row per variable in the template with its state labels.

    Useful for a `display(...)` cell that documents the bins used by the
    learner. Interval labels are pretty-printed via `format_bin_label`.
    """
    rows = []
    for i, name in template:
        var = template.variable(i)
        labels = list(var.labels())
        pretty = [format_bin_label(lab, decimals) for lab in labels]
        rows.append({"variable": name, "n_states": len(labels), "labels": pretty})
    return pd.DataFrame(rows)
