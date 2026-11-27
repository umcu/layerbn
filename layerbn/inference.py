"""Mutual information and structural relations, for reading a learned network.

`mutual_information_scores` ranks variables by how much they tell you about a
target, in bits, computed from the joint distribution of the network.

`relations_to_target` says how each variable is connected to the target in
the learned structure: as a parent, as a child, as a co-parent (a variable
that shares a child with the target) or not directly.

Mutual information alone does not say whether a variable is directly
connected to the target or only related to it through other variables.
Together the two give both pieces of information.

Mutual information *given the target's parents* is deliberately not offered.
In a Bayesian network every variable is independent of its non-descendants
given its parents, so that quantity is exactly zero for everything except
the target's descendants and says nothing about the data.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from typing import Any

import pandas as pd


def mutual_information_scores(
    bn: Any,
    target: str,
    *,
    exclude: Iterable[str] = (),
    verbose: bool = False,
) -> pd.Series:
    """Mutual information (bits) of every other variable with `target`.

    Returns a Series indexed by column name, largest first. A variable for
    which the computation fails gets `NaN`, so a gap is visible.
    """
    import pyagrum as gum

    skipped = set(exclude) | {target}
    scores: dict[str, float] = {}
    for column in (v for v in bn.names() if v not in skipped):
        try:
            # A new engine per variable: InformationTheory restricts the
            # engine it is given to that query's variables, so a shared
            # engine fails for every variable after the first.
            info = gum.InformationTheory(gum.LazyPropagation(bn), target, [column])
            scores[column] = max(info.mutualInformationXY(), 0.0)
        except Exception as exc:
            if verbose:
                print(f"MI({column}; {target}) failed: {exc}")
            scores[column] = float("nan")
    return pd.Series(scores, name=f"MI with {target}").sort_values(
        ascending=False, na_position="last")


def relations_to_target(bn: Any, target: str) -> dict[str, tuple[str, int | None]]:
    """For each variable: its relation to `target`, and its distance in arcs.

    Relations: `parent`, `child`, `co-parent` (shares a child with the target),
    `other`. The distance is the number of arcs on the shortest path between
    the two variables, ignoring arc direction; `None` if they are not
    connected at all.
    """
    target_id = bn.idFromName(target)
    name = bn.variable
    parents = set(bn.parents(target_id))
    children = set(bn.children(target_id))
    coparents = {p for child in children for p in bn.parents(child)} - {target_id}

    neighbours: dict[int, set[int]] = {
        i: set(bn.parents(i)) | set(bn.children(i)) for i in bn.nodes()}
    distance = {target_id: 0}
    queue = deque([target_id])
    while queue:
        current = queue.popleft()
        for other in neighbours[current]:
            if other not in distance:
                distance[other] = distance[current] + 1
                queue.append(other)

    out: dict[str, tuple[str, int | None]] = {}
    for i in bn.nodes():
        if i == target_id:
            continue
        if i in parents:
            relation = "parent"
        elif i in children:
            relation = "child"
        elif i in coparents:
            relation = "co-parent"
        else:
            relation = "other"
        out[name(i).name()] = (relation, distance.get(i))
    return out
