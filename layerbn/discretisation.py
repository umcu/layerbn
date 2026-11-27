"""Discretisation: turning continuous variables into bins.

Bayesian networks here work on discrete variables, so a continuous variable
is cut into bins. Every result depends on these bins, which is why the bin
edges are reported with the results.

The default method and number of bins come from the settings. A variable can
override them in the design table: `bins` for a different number of bins,
`cutpoints` for thresholds you choose (for example a clinical cut-off), or
`type` to force a variable to be treated as categorical or as continuous.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from layerbn.design import Design
from layerbn.settings import Discretisation


def make_type_processor(
    df: pd.DataFrame | None = None,
    design: Design | None = None,
    discretisation: Discretisation | None = None,
    *,
    method: str | None = None,
    bins: int | None = None,
    categorical_max_levels: int | None = None,
    fixed_states: dict[str, list[str]] | None = None,
) -> Any:
    """Build the pyAgrum discretiser.

    The defaults come from `discretisation` (or the keyword arguments).
    Per-variable overrides are read from `design`; `df` is needed for them,
    because cut points need the range of the data and a variable forced to
    be categorical needs its observed values.
    """
    from pyagrum.lib.discreteTypeProcessor import DiscreteTypeProcessor

    base = discretisation or Discretisation()
    processor = DiscreteTypeProcessor(
        defaultDiscretizationMethod=method or base.method,
        defaultNumberOfBins=bins or base.bins,
        discretizationThreshold=(categorical_max_levels
                                 if categorical_max_levels is not None
                                 else base.categorical_max_levels),
    )
    if design is None or df is None:
        return processor

    fixed_states = fixed_states or {}
    for v in design.variables:
        if v.column not in df.columns:
            continue
        series = df[v.column]
        if v.column in fixed_states:
            # Already cut by `with_missing_category`; keep its states and order.
            _keep_as_categories(processor, v.column, fixed_states[v.column], ordered=True)
        elif v.cutpoints:
            low = min(float(series.min()), v.cutpoints[0]) - 1.0
            high = max(float(series.max()), v.cutpoints[-1]) + 1.0
            processor.setDiscretizationParameters(
                v.column, "expert", [low, *v.cutpoints, high])
        elif v.kind == "categorical":
            _keep_as_categories(processor, v.column, series.dropna().unique().tolist())
        elif v.bins is not None or v.kind == "continuous":
            processor.setDiscretizationParameters(
                v.column, method or base.method, v.bins or bins or base.bins)
    return processor


def _keep_as_categories(processor: Any, column: str, values: list[Any], *,
                        ordered: bool = False) -> None:
    """Tell pyAgrum not to bin `column` and to use `values` as its categories.

    pyAgrum changed what it accepts here between 2.1 and 2.3: a list of the
    values first, then a string in its own shorthand (`{a|b|c}`). Try the list
    and fall back to the shorthand, so both work.
    """
    values = list(values) if ordered else sorted(values, key=lambda v: (str(type(v)), v))
    try:
        processor.setDiscretizationParameters(column, "NoDiscretization", values)
    except ValueError:
        processor.setDiscretizationParameters(
            column, "NoDiscretization", "{" + "|".join(str(v) for v in values) + "}")


# ---------------------------------------------------------------------------
# missingness as a state
# ---------------------------------------------------------------------------

MISSING = "Missing"


def with_missing_category(
    series: pd.Series,
    *,
    kind: str | None = None,
    bins: int | None = None,
    cutpoints: Sequence[float] = (),
    method: str = "quantile",
    default_bins: int = 4,
    categorical_max_levels: int = 10,
) -> tuple[pd.Series, list[str]]:
    """Replace the missing values of one variable by a state called `Missing`.

    A continuous variable is first cut into bins from its observed values
    (same rules as the normal binning: cut points, number of bins, method),
    then `Missing` is added as a last state. A categorical variable keeps its
    categories and gains `Missing`. Returns the new column (text) and the
    states in order. The network can then learn whether missingness itself is
    informative, for example a test that is missing because the person was too
    unwell to take it.
    """
    observed = series.dropna()
    numeric = pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)
    binned = numeric and (kind == "continuous" or bool(cutpoints) or bins is not None
                          or (kind is None and observed.nunique() > categorical_max_levels))
    if kind == "categorical":
        binned = False

    if binned:
        x = observed.to_numpy(dtype=float)
        if cutpoints:
            inner = sorted(float(c) for c in cutpoints)
            edges = [min(x.min(), inner[0]) - 1.0, *inner, max(x.max(), inner[-1]) + 1.0]
        else:
            k = bins or default_bins
            edges = (np.quantile(x, np.linspace(0, 1, k + 1)) if method == "quantile"
                     else np.linspace(x.min(), x.max(), k + 1))
            edges = sorted({float(e) for e in edges})
            if len(edges) < 3:                       # constant-ish: one bin
                edges = [edges[0] - 1.0, edges[-1] + 1.0]
        names = [f"[{lo:.6g};{hi:.6g}{']' if i == len(edges) - 2 else '['}"
                 for i, (lo, hi) in enumerate(zip(edges[:-1], edges[1:], strict=True))]
        index = np.clip(np.digitize(series.to_numpy(dtype=float), edges[1:-1],
                                    right=False), 0, len(names) - 1)
        out = pd.Series(np.array(names, dtype=object)[index], index=series.index)
        out[series.isna()] = MISSING
        return out, [*names, MISSING]

    values = observed
    if numeric and (observed == observed.round()).all():
        values = observed.astype("int64")
    states = [str(v) for v in sorted(values.unique())]
    out = series.map(lambda v: MISSING if pd.isna(v) else
                     (str(int(v)) if numeric and v == round(v) else str(v)))
    return out, [*[s for s in states if s != MISSING], MISSING]


# ---------------------------------------------------------------------------
# reading and writing bin labels
# ---------------------------------------------------------------------------

_INTERVAL_RE = re.compile(r"^[\[\(]\s*([-+0-9.eE]+)\s*;\s*([-+0-9.eE]+)\s*[\[\]\)]$")


def _bounds(label: str) -> tuple[float, float] | None:
    match = _INTERVAL_RE.match(label.strip())
    return (float(match.group(1)), float(match.group(2))) if match else None


def _number(x: float) -> str:
    """A bin edge as a short number: 3 significant digits, no trailing zeros."""
    if abs(x) >= 100:
        text = f"{x:.0f}"
    elif abs(x) >= 10:
        text = f"{x:.1f}"
    else:
        text = f"{x:.2f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def pretty_labels(labels: Sequence[str]) -> dict[str, str]:
    """Readable names for the states of a variable.

    Interval states become `< 24`, `24 to < 27` and `≥ 27`. Other states
    (categories) are returned unchanged.
    """
    parsed = [(lab, _bounds(lab)) for lab in labels if lab != MISSING]
    if not parsed or any(b is None for _, b in parsed):
        return {lab: lab for lab in labels}
    ordered = sorted(parsed, key=lambda item: item[1])
    out: dict[str, str] = {MISSING: MISSING} if MISSING in labels else {}
    last = len(ordered) - 1
    for i, (lab, (lo, hi)) in enumerate(ordered):
        if len(ordered) == 1:
            out[lab] = f"{_number(lo)} to {_number(hi)}"
        elif i == 0:
            out[lab] = f"< {_number(hi)}"
        elif i == last:
            out[lab] = f"≥ {_number(lo)}"
        else:
            out[lab] = f"{_number(lo)} to < {_number(hi)}"
    return out


def state_for_value(labels: Sequence[str], value: Any) -> str | None:
    """Find the state a raw value belongs to.

    An exact match of the text wins. Otherwise, if the states are intervals
    and the value is a number, the interval containing it is returned (the
    first or last interval for a value outside the range). Returns `None`
    when the value cannot be placed.
    """
    labels = list(labels)
    if value is None or (isinstance(value, float) and value != value):
        return MISSING if MISSING in labels else None
    if isinstance(value, bool):
        # YAML reads an unquoted `Yes` or `No` as true or false. Match it to the
        # category the data uses, whatever the spelling.
        words = ("yes", "ja", "true", "1") if value else ("no", "nee", "false", "0")
        for label in labels:
            if str(label).strip().lower() in words:
                return label
        return None
    if str(value) in labels:
        return str(value)
    # A readable name as shown in the tables, such as "≥ 27".
    for raw, pretty in pretty_labels(labels).items():
        if str(value).strip() == pretty:
            return raw
    try:
        numeric = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None

    bins: list[tuple[float, float, str]] = []
    for lab in (lab for lab in labels if lab != MISSING):
        bounds = _bounds(lab)
        if bounds is None:
            return None
        bins.append((bounds[0], bounds[1], lab))
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


def describe_template(template: Any, design: Design | None = None) -> pd.DataFrame:
    """One row per variable: how it was binned and what its states are."""
    rows = []
    for i, name in template:
        labels = list(template.variable(i).labels())
        core = [lab for lab in labels if lab != MISSING]
        binned = bool(core) and all(_bounds(lab) is not None for lab in core)
        pretty = pretty_labels(labels)
        label = design.label(name) if design is not None else name
        ordered = (sorted(core, key=_bounds) + ([MISSING] if MISSING in labels else [])
                   if binned else labels)
        rows.append({
            "Variable": label,
            "Treated as": "continuous, binned" if binned else "categorical",
            "States": len(labels),
            "Bins or categories": " | ".join(pretty[lab] for lab in ordered),
            # The readable names are rounded. These are the exact edges used.
            "Exact edges": " | ".join(o for o in ordered if o != MISSING) if binned else "",
        })
    return pd.DataFrame(rows)
