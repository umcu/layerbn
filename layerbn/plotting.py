"""Bayesian-network plotting helpers.

Semantic wrappers around `pyagrum.lib.notebook.showBN` / `showInference`
and `pyagrum.lib.image.export*` — build a per-layer colour scale,
translate that into a per-node `nodeColor` dict, and expose one call
that both shows the figure and writes a PDF (editable in Illustrator).

Also provides the single-knob sensitivity plot used by `plot_knob_sweep`.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def default_layer_colors(
    layer_order: Sequence[str],
    *,
    min_val: float = 0.111111,
    max_val: float = 0.99999,
) -> dict[str, float]:
    """Evenly-spaced colour intensity per layer, in the given order.

    Values are meant to be looked up in a matplotlib colormap by pyAgrum's
    `cmapNode` argument.
    """
    if len(layer_order) < 2:
        return {name: (min_val + max_val) / 2 for name in layer_order}
    step = (max_val - min_val) / (len(layer_order) - 1)
    return {name: min_val + i * step for i, name in enumerate(layer_order)}


def build_node_colors(
    bn: Any,
    layer_map: Mapping[str, Sequence[str]],
    layer_color_map: Mapping[str, float],
    *,
    default: float = 0.5,
) -> dict[str, float]:
    """Return `{variable_name: color_value}` for every variable in `bn`."""
    node_colors: dict[str, float] = {}
    for layer, variables in layer_map.items():
        colour = layer_color_map.get(layer, default)
        for var in variables:
            if var in bn.names():
                node_colors[var] = colour
    return node_colors


def show_and_save_bn(
    bn: Any,
    *,
    save_path: str | Path,
    inference: bool = False,
    show: bool = True,
    **kwargs: Any,
) -> Path:
    """Render `bn` in the notebook and export a PDF.

    Extra kwargs (arcWidth, nodeColor, arcColor, cmapNode, cmapArc, size,
    ...) are forwarded to both the notebook renderer and the exporter.
    """
    from pyagrum.lib import image as gumimage
    from pyagrum.lib import notebook as gnb

    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    if show:
        if inference:
            gnb.showInference(bn, **kwargs)
        else:
            gnb.showBN(bn, **kwargs)

    if inference:
        gumimage.exportInference(bn, str(save_path), **kwargs)
    else:
        gumimage.export(bn, str(save_path), **kwargs)
    return save_path


def plot_knob_sweep(sweep_df: pd.DataFrame, meta: dict[str, Any]) -> None:
    """Line + 95%-CI ribbon plot, one panel per outcome.

    `sweep_df` and `meta` are the return values of
    `layerbn.bn_utils.bootstrap_knob_sweep`.
    """
    import matplotlib.pyplot as plt

    knob = meta["knob"]
    knob_states = meta["knob_states"]
    outcomes = meta["outcomes"]
    x = np.arange(len(knob_states))

    palette = {"No": "#2a9d8f", "Unobserved": "#9aa0a6", "Yes": "#e76f51"}
    cycle = ["#264653", "#e9c46a", "#e76f51", "#2a9d8f", "#9aa0a6"]

    fig, axes = plt.subplots(
        len(outcomes), 1, figsize=(7.6, 4.5 * len(outcomes)), squeeze=False,
    )
    axes = axes[:, 0]

    handles, labels = [], []
    for ax, outcome in zip(axes, outcomes, strict=False):
        ax.set_facecolor("#fbfbfb")
        sub = sweep_df[sweep_df["Outcome"] == outcome]
        states = meta["outcome_states"][outcome]
        top = 0.0
        for j, state in enumerate(states):
            d = (sub[sub["Outcome state"] == state]
                 .set_index(knob).reindex(knob_states))
            colour = palette.get(state, cycle[j % len(cycle)])
            ax.fill_between(x, d["CI_low"], d["CI_high"], color=colour,
                            alpha=0.16, linewidth=0)
            line, = ax.plot(
                x, d["P"], "-o", color=colour, lw=2.7, ms=8,
                markeredgecolor="white", markeredgewidth=1.4,
                label=state, zorder=3,
            )
            top = max(top, float(np.nanmax(d["CI_high"])))
            if outcome == outcomes[0]:
                handles.append(line)
                labels.append(state)
            if state == "Yes":
                for xi, yi in zip(x, d["P"], strict=False):
                    if np.isfinite(yi):
                        ax.annotate(
                            f"{yi:.0%}", (xi, yi), textcoords="offset points",
                            xytext=(0, 11), ha="center", fontsize=8.5,
                            fontweight="bold", color=colour,
                        )
        ax.set_title(outcome, fontsize=12, fontweight="bold", pad=8)
        ax.set_xlabel(knob, fontweight="bold", labelpad=8)
        ax.set_ylabel("posterior probability", fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(knob_states)
        ax.set_ylim(0, min(1.0, top * 1.20))
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.3)
        ax.set_axisbelow(True)

    fig.legend(
        handles, labels, loc="upper center", ncol=len(labels),
        frameon=False, fontsize=10, bbox_to_anchor=(0.5, 0.945),
        title="outcome state",
    )
    fig.suptitle(
        f"Outcome probabilities across {knob}\n"
        "fixed patient profile · shaded = 95% bootstrap interval",
        fontsize=13, fontweight="bold", y=1.0,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    plt.show()
