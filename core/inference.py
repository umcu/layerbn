"""Mutual-information rankings for interpretability.

Wraps `pyagrum.InformationTheory` to produce a sortable pandas Series
of per-variable importance for a target outcome — either raw MI or
conditional MI given the outcome's parents (i.e. what a variable adds
beyond what's already captured by the outcome's Markov blanket).
"""
from __future__ import annotations

from typing import Any, Iterable

import pandas as pd


def mutual_information_scores(
    bn: Any,
    target: str,
    *,
    exclude: Iterable[str] = (),
    verbose: bool = False,
) -> pd.Series:
    """Rank variables by raw MI with `target`, computed on the joint BN.

    Returns a Series indexed by variable name, sorted descending. Variables
    listed in `exclude` (plus `target` itself) are skipped.
    """
    import pyagrum as gum
    ie = gum.LazyPropagation(bn)

    exclude_set = set(exclude) | {target}
    candidates = [v for v in bn.names() if v not in exclude_set]
    scores: dict[str, float] = {}
    for var in candidates:
        try:
            it = gum.InformationTheory(ie, target, [var])
            scores[var] = it.mutualInformationXY()
        except Exception as exc:
            if verbose:
                print(f"MI({var} → {target}) failed: {exc}")
    return pd.Series(scores, name=f"MI(·; {target})").sort_values(ascending=False)


def conditional_mutual_information_scores(
    bn: Any,
    target: str,
    *,
    conditioning_set: Iterable[str] | None = None,
    exclude: Iterable[str] = (),
    verbose: bool = False,
) -> pd.Series:
    """Rank variables by CMI with `target` given `conditioning_set`.

    When `conditioning_set` is None, the target's parents in `bn` are used
    — a standard "does this variable add anything beyond the Markov
    blanket" check. Variables in the conditioning set are auto-excluded
    from the ranking.
    """
    import pyagrum as gum
    ie = gum.LazyPropagation(bn)

    if conditioning_set is None:
        target_id = bn.idFromName(target)
        conditioning = [bn.variable(p).name() for p in bn.parents(target_id)]
    else:
        conditioning = list(conditioning_set)

    exclude_set = set(exclude) | {target} | set(conditioning)
    candidates = [v for v in bn.names() if v not in exclude_set]
    scores: dict[str, float] = {}
    for var in candidates:
        try:
            it = gum.InformationTheory(ie, target, [var], conditioning)
            scores[var] = it.mutualInformationXYgivenZ()
        except Exception as exc:
            if verbose:
                print(f"CMI({var} → {target} | {conditioning}) failed: {exc}")
    return pd.Series(scores, name=f"CMI(·; {target} | parents)").sort_values(ascending=False)
