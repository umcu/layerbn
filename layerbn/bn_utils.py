"""Structure learning, bootstrap and inference.

Nothing here knows what a variable means. A network is learned from a data
frame and an ordered mapping `{layer name: [column, ...]}`. The order of that
mapping is the constraint: an arc may only run from a layer to itself or to a
layer further down.

Further rules are passed as plain arguments: pairs of columns that are
forbidden or required, columns that may have no parents or no children, and
layers in which arcs between members are not allowed.

`layerbn.analysis.Analysis` calls these functions with every argument filled
in from the project. Call them directly only when you need something it does
not offer.
"""
from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from itertools import product
from typing import Any

import numpy as np
import pandas as pd

Progress = Callable[[], None]


def flatten(layer_map: Mapping[str, Sequence[str]]) -> list[str]:
    """Every column of a layer map, in layer order."""
    return [column for members in layer_map.values() for column in members]


def configure_structure(
    learner: Any,
    layer_map: Mapping[str, Sequence[str]],
    *,
    no_inner_arcs: Iterable[str] = (),
    forbidden_pairs: Iterable[tuple[str, str]] = (),
    mandatory_pairs: Iterable[tuple[str, str]] = (),
    no_parents: Iterable[str] = (),
    no_children: Iterable[str] = (),
) -> None:
    """Restrict a pyAgrum learner to the arcs the layer order allows.

    * An arc may run from a layer to itself or to a later layer, never back.
    * `no_inner_arcs` names layers in which members may not be connected.
    * `forbidden_pairs` are further `(parent, child)` arcs ruled out.
    * `mandatory_pairs` are arcs the learner must include.
    * `no_parents` / `no_children` pin variables as roots or as sinks.

    A pair that is both mandatory and forbidden raises `ValueError` here,
    because pyAgrum's own message does not say which pair is at fault.
    """
    names = list(layer_map)
    columns = set(flatten(layer_map))
    no_inner = set(no_inner_arcs)
    forbidden = set(forbidden_pairs)
    mandatory = {p for p in mandatory_pairs if p[0] in columns and p[1] in columns}

    conflict = forbidden & mandatory
    if conflict:
        raise ValueError(f"these arcs are both required and forbidden: {sorted(conflict)}")

    allowed: set[tuple[str, str]] = set()
    for i, from_name in enumerate(names):
        for j in range(i, len(names)):
            to_name = names[j]
            if i == j and from_name in no_inner:
                continue
            allowed.update(product(layer_map[from_name], layer_map[to_name]))
    allowed -= forbidden

    for parent in columns:
        for child in columns:
            if parent != child and (parent, child) not in allowed:
                learner.addForbiddenArc(parent, child)

    for column in sorted(set(no_parents) & columns):
        learner.addNoParentNode(column)
    for column in sorted(set(no_children) & columns):
        learner.addNoChildrenNode(column)
    # Required arcs last: pyAgrum checks them against the rules above.
    for parent, child in sorted(mandatory):
        learner.addMandatoryArc(parent, child)


def build_bn(
    df: pd.DataFrame,
    layer_map: Mapping[str, Sequence[str]],
    type_processor: Any,
    *,
    score: str = "K2",
    search: str = "tabu",
    max_parents: int = 5,
    seed: int = 42,
    fixed_template: Any = None,
    enforce_structure: bool = True,
    no_inner_arcs: Iterable[str] = (),
    forbidden_pairs: Iterable[tuple[str, str]] = (),
    mandatory_pairs: Iterable[tuple[str, str]] = (),
    no_parents: Iterable[str] = (),
    no_children: Iterable[str] = (),
) -> Any:
    """Learn a layered Bayesian network with pyAgrum.

    Parameters
    ----------
    df : DataFrame
        Complete data. Only the columns in `layer_map` are used.
    layer_map : mapping
        `{layer name: [column, ...]}` in causal order.
    type_processor : DiscreteTypeProcessor
        From `layerbn.discretisation.make_type_processor`.
    score : {"K2", "BIC", "BDeu"}
        The structure score. K2 and BDeu contain their own prior. BIC does
        not, so a smoothing prior is added for BIC only: a parent
        configuration that nobody in a resample happens to occupy then gets
        a small probability instead of zero. Adding a second prior to K2 or
        BDeu would count the prior twice.
    search : {"tabu", "greedy"}
        Tabu search explores more than greedy hill climbing and is slower.
    fixed_template : optional
        A discretisation computed once from the full data. Bootstrap
        resamples should share it so that every resample uses the same bins.
    enforce_structure : bool
        With False every rule, including the layer order, is skipped. That
        is an unconstrained search, useful as a comparison and not as the
        analysis.
    """
    import pyagrum as gum

    random.seed(seed)
    np.random.seed(seed)

    columns = flatten(layer_map)
    data = df[columns]
    template = (fixed_template if fixed_template is not None
                else type_processor.discretizedTemplate(data))
    learner = gum.BNLearner(data, template)

    score = score.upper()
    if score == "K2":
        learner.useScoreK2()
    elif score == "BIC":
        learner.useScoreBIC()
        learner.useSmoothingPrior()
    elif score == "BDEU":
        learner.useScoreBDeu()
    else:
        raise ValueError(f"Unsupported score {score!r}: choose K2, BIC or BDeu")

    if search == "tabu":
        learner.useLocalSearchWithTabuList()
    elif search == "greedy":
        learner.useGreedyHillClimbing()
    else:
        raise ValueError(f"Unsupported search {search!r}: choose tabu or greedy")

    if enforce_structure:
        configure_structure(
            learner, layer_map, no_inner_arcs=no_inner_arcs,
            forbidden_pairs=forbidden_pairs, mandatory_pairs=mandatory_pairs,
            no_parents=no_parents, no_children=no_children)

    learner.setMaxIndegree(max_parents)
    return learner.learnBN()


# ---------------------------------------------------------------------------
# bootstrap
# ---------------------------------------------------------------------------

def _resample(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    return df.sample(frac=1.0, replace=True, random_state=seed)


def bootstrap_edge_frequencies(
    df: pd.DataFrame,
    *,
    layer_map: Mapping[str, Sequence[str]],
    type_processor: Any,
    resamples: int = 200,
    seed: int = 42,
    progress: Progress | None = None,
    **build_kwargs: Any,
) -> tuple[dict[tuple[str, str], float], int]:
    """Learn the network on `resamples` bootstrap samples; count each arc.

    Returns `(frequencies, failed)`. A frequency is the fraction of
    resamples in which the arc occurs. The denominator is `resamples`, not
    the number of fits that succeeded, so a failed fit lowers every
    frequency instead of being left out of the calculation.
    """
    counts: dict[tuple[str, str], int] = defaultdict(int)
    failed = 0
    for i in range(resamples):
        if progress:
            progress()
        try:
            bn = build_bn(_resample(df, seed + i), layer_map, type_processor,
                          seed=seed + i, **build_kwargs)
        except Exception:
            failed += 1
            continue
        for parent_id, child_id in bn.arcs():
            counts[(bn.variable(parent_id).name(), bn.variable(child_id).name())] += 1
    return {arc: n / resamples for arc, n in counts.items()}, failed


def _interval(values: Sequence[float]) -> tuple[float, float, float, float]:
    arr = np.asarray(values, float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return (np.nan, np.nan, np.nan, np.nan)
    return (arr.mean(), arr.std(ddof=1) if arr.size > 1 else 0.0,
            np.quantile(arr, 0.025), np.quantile(arr, 0.975))


def bootstrap_profile_risks(
    df: pd.DataFrame,
    *,
    layer_map: Mapping[str, Sequence[str]],
    type_processor: Any,
    profiles: Sequence[tuple[str, Mapping[str, int]]],
    targets: Sequence[str],
    resamples: int = 200,
    seed: int = 42,
    progress: Progress | None = None,
    **build_kwargs: Any,
) -> tuple[pd.DataFrame, int]:
    """Probability of each state of each target, given each profile.

    `profiles` holds `(name, {column: state index})`. Every resample learns
    the structure and the parameters again, so the interval covers
    uncertainty in both. Pass `fixed_template` so that a state index refers
    to the same bin in every resample.

    Returns `(table, failed)`.
    """
    import pyagrum as gum

    samples: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    labels: dict[str, list[str]] = {}
    failed = 0

    for i in range(resamples):
        if progress:
            progress()
        try:
            bn = build_bn(_resample(df, seed + i), layer_map, type_processor,
                          seed=seed + i, **build_kwargs)
        except Exception:
            failed += 1
            continue
        for name, evidence in profiles:
            engine = gum.LazyPropagation(bn)
            try:
                engine.setEvidence(dict(evidence))
            except Exception:
                continue
            for target in targets:
                if target not in labels:
                    labels[target] = list(bn.variable(bn.idFromName(target)).labels())
                posterior = engine.posterior(target)
                for index, state in enumerate(labels[target]):
                    samples[(name, target, state)].append(float(posterior[index]))

    rows = []
    for (name, target, state), values in samples.items():
        mean, std, low, high = _interval(values)
        if np.isnan(mean):
            continue
        rows.append({"profile": name, "target": target, "state": state,
                     "probability": mean, "std": std, "ci_low": low,
                     "ci_high": high, "resamples": len(values)})
    columns = ["profile", "target", "state", "probability", "std",
               "ci_low", "ci_high", "resamples"]
    return pd.DataFrame(rows, columns=columns), failed


def bootstrap_sweep(
    df: pd.DataFrame,
    *,
    layer_map: Mapping[str, Sequence[str]],
    type_processor: Any,
    variable: str,
    variable_states: Sequence[str],
    fixed: Mapping[str, int],
    targets: Sequence[str],
    resamples: int = 200,
    seed: int = 42,
    progress: Progress | None = None,
    **build_kwargs: Any,
) -> tuple[pd.DataFrame, dict[str, list[str]], int]:
    """Move one variable across its states and read the targets.

    `fixed` holds `{column: state index}` held constant. Returns
    `(table, target_states, failed)`; the table has one row per target,
    state of `variable` and state of the target.
    """
    import pyagrum as gum

    samples: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    target_states: dict[str, list[str]] = {}
    failed = 0

    for i in range(resamples):
        if progress:
            progress()
        try:
            bn = build_bn(_resample(df, seed + i), layer_map, type_processor,
                          seed=seed + i, **build_kwargs)
        except Exception:
            failed += 1
            continue
        for target in targets:
            target_states.setdefault(
                target, list(bn.variable(bn.idFromName(target)).labels()))
        for index, state in enumerate(variable_states):
            try:
                engine = gum.LazyPropagation(bn)
                engine.setEvidence({**fixed, variable: index})
                posterior = {t: engine.posterior(t) for t in targets}
            except Exception:
                continue
            for target in targets:
                for s_index, s_label in enumerate(target_states[target]):
                    samples[(target, state, s_label)].append(
                        float(posterior[target][s_index]))

    rows = []
    for (target, state, target_state), values in samples.items():
        mean, _, low, high = _interval(values)
        if np.isnan(mean):
            continue
        rows.append({"target": target, "variable_state": state,
                     "target_state": target_state, "probability": mean,
                     "ci_low": low, "ci_high": high, "resamples": len(values)})
    if not rows:
        raise RuntimeError(
            "No valid result was produced. Check the fixed values: none of the "
            "resamples could use them as evidence.")
    columns = ["target", "variable_state", "target_state", "probability",
               "ci_low", "ci_high", "resamples"]
    return pd.DataFrame(rows, columns=columns), target_states, failed


def descendants(bn: Any, start_id: int) -> set[int]:
    """All nodes reachable from `start_id` by following arcs downstream."""
    seen: set[int] = set()
    stack = [start_id]
    while stack:
        for child in bn.children(stack.pop()):
            if child not in seen:
                seen.add(child)
                stack.append(child)
    return seen
