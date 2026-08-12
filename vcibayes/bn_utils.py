"""Bayesian network structure learning, bootstrapping, and scenarios.

Everything cohort-specific is a parameter: which layers to exclude, which
layer names mark the outcome and dropout roles, the score, the seed. No
cohort's conventions are assumed.

These functions take the layer map, the discretisation and the layer role
patterns as separate arguments, which means a caller has to keep them
consistent with the spec at every call site. `vcibayes.analysis.Analysis`
does that for you and is the recommended entry point; use these directly
when you need control it does not expose.
"""
from __future__ import annotations

import random
from collections import defaultdict
from itertools import product
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from vcibayes.discretisation import state_for_value

# Layer-name substrings that identify semantic roles. Override when your
# cohort names its layers differently.
DEFAULT_OUTCOME_LAYER_PATTERNS: tuple[str, ...] = ("Outcomes",)
DEFAULT_DROPOUT_LAYER_PATTERNS: tuple[str, ...] = ("Dropout",)


def _match_any(layer_name: str, patterns: Sequence[str]) -> bool:
    return any(p in layer_name for p in patterns)


def collect_outcome_vars(
    layer_map: Mapping[str, Sequence[str]],
    *,
    outcome_patterns: Sequence[str] = DEFAULT_OUTCOME_LAYER_PATTERNS,
    dropout_patterns: Sequence[str] = DEFAULT_DROPOUT_LAYER_PATTERNS,
) -> tuple[list[str], list[str]]:
    """Return `(outcome_vars, dropout_vars)` inferred from layer names."""
    outcome_vars: list[str] = []
    dropout_vars: list[str] = []
    for layer, variables in layer_map.items():
        if _match_any(layer, dropout_patterns):
            dropout_vars.extend(variables)
        elif _match_any(layer, outcome_patterns):
            outcome_vars.extend(variables)
    return outcome_vars, dropout_vars


def configure_guided_structure(
    learner: Any,
    layer_map_filtered: Mapping[str, Sequence[str]],
    variables_to_keep: Sequence[str],
    outcomes: Sequence[str],
    *,
    dropout_patterns: Sequence[str] = DEFAULT_DROPOUT_LAYER_PATTERNS,
    within_layers: bool = True,
    arcs_between_outcomes: bool = False,
    selection_parents: str = "outcomes",
    forbidden_pairs: Iterable[tuple[str, str]] = (),
    mandatory_pairs: Iterable[tuple[str, str]] = (),
    no_parents: Iterable[str] = (),
    no_children: Iterable[str] = (),
) -> tuple[list[str], list[str]]:
    """Restrict the learner to arcs that go downward through the layers.

    Rules always encoded:

    * Arcs may only go from an earlier layer to the same or a later layer.

    Rules that the keyword arguments control, whose defaults reproduce the
    behaviour this function had before they existed:

    * `within_layers` — whether two variables in the same layer may be
      connected. False makes each layer internally independent.
    * `arcs_between_outcomes` — whether one outcome may point at another.
    * `selection_parents` — `"outcomes"` allows arcs into a dropout-layer
      variable only from an outcome, on the grounds that dropout follows
      the outcomes rather than the covariates. `"any"` drops that
      restriction and lets the layer order alone decide.

    Additional structural knowledge:

    * `forbidden_pairs` — `(parent, child)` arcs to rule out even though
      the layer order permits them.
    * `mandatory_pairs` — arcs the learner must include. These must be
      consistent with everything above; a pair that is both mandatory and
      forbidden raises `ValueError` rather than reaching pyAgrum, whose own
      message does not say which pair was at fault.
    * `no_parents` / `no_children` — variables pinned as roots or sinks.

    Returns `(dropout_vars, true_outcomes)` for the caller to reuse when
    adding hard outcome→dropout arcs after learning.
    """
    if selection_parents not in ("outcomes", "any"):
        raise ValueError(
            f"selection_parents must be 'outcomes' or 'any', got {selection_parents!r}")

    layer_keys = list(layer_map_filtered.keys())
    dropout_vars = [v for k in layer_keys if _match_any(k, dropout_patterns)
                    for v in layer_map_filtered[k]]
    true_outcomes = [v for v in outcomes if v not in dropout_vars]

    keep = set(variables_to_keep)
    forbidden_pairs = set(forbidden_pairs)
    mandatory_pairs = set(mandatory_pairs)
    no_parents = set(no_parents)
    no_children = set(no_children)

    conflict = forbidden_pairs & mandatory_pairs
    if conflict:
        raise ValueError(
            f"these arcs are both mandatory and forbidden: {sorted(conflict)}")

    allowed_arcs: list[tuple[str, str]] = []
    for i, from_key in enumerate(layer_keys):
        for j, to_key in enumerate(layer_keys[i:], start=i):
            if i == j and not within_layers:
                continue
            for parent, child in product(layer_map_filtered[from_key],
                                          layer_map_filtered[to_key]):
                if child in dropout_vars and selection_parents == "outcomes":
                    if parent in outcomes:
                        allowed_arcs.append((parent, child))
                    continue
                if parent in keep and child in keep:
                    allowed_arcs.append((parent, child))

    allowed_set = set(allowed_arcs) - forbidden_pairs
    for parent in variables_to_keep:
        for child in variables_to_keep:
            if parent != child and (parent, child) not in allowed_set:
                learner.addForbiddenArc(parent, child)

    if not arcs_between_outcomes:
        for parent in true_outcomes:
            for child in true_outcomes:
                if parent != child:
                    learner.addForbiddenArc(parent, child)

    # Node-level constraints are applied after the pairwise ones so that a
    # variable pinned as a root or a sink stays that way regardless of what
    # the layer order allowed.
    for variable in sorted(no_parents & keep):
        learner.addNoParentNode(variable)
    for variable in sorted(no_children & keep):
        learner.addNoChildrenNode(variable)

    # Mandatory arcs come last: pyAgrum resolves them against the
    # constraints already registered.
    for parent, child in sorted(mandatory_pairs):
        if parent in keep and child in keep:
            learner.addMandatoryArc(parent, child)

    return dropout_vars, true_outcomes


def build_bn(
    df: pd.DataFrame,
    outcomes: Sequence[str],
    layer_map: Mapping[str, Sequence[str]],
    type_processor: Any,
    *,
    score: str = "K2",
    use_tabu: bool = True,
    random_seed: int = 42,
    enforce_structure: bool = True,
    fixed_template: Any = None,
    use_smoothing: bool = False,
    exclude_layers: Iterable[str] = (),
    max_indegree: int = 5,
    outcome_patterns: Sequence[str] = DEFAULT_OUTCOME_LAYER_PATTERNS,
    dropout_patterns: Sequence[str] = DEFAULT_DROPOUT_LAYER_PATTERNS,
    within_layers: bool = True,
    arcs_between_outcomes: bool = False,
    selection_parents: str = "outcomes",
    forbidden_pairs: Iterable[tuple[str, str]] = (),
    mandatory_pairs: Iterable[tuple[str, str]] = (),
    no_parents: Iterable[str] = (),
    no_children: Iterable[str] = (),
) -> Any:
    """Learn a layered Bayesian network with pyAgrum.

    Parameters
    ----------
    df : DataFrame
        Fully-imputed input data. Columns not needed as outcomes and not
        listed in `exclude_layers` become learnable nodes.
    outcomes : sequence of str
        Outcome variable names to keep in the network. Any *other* variable
        that belongs to an outcome/dropout layer is dropped before learning.
    layer_map : mapping
        `{layer_name: [variable, ...]}` defining the expert layering.
    type_processor : DiscreteTypeProcessor
        Constructed via `vcibayes.discretisation.make_type_processor`.
    score : {"K2", "BIC", "BDeu"}
        Structure-learning score.
    fixed_template : optional
        Use a pre-computed discretisation template so bootstrap resamples
        share bin edges. Build once with `type_processor.discretizedTemplate(df)`.
    exclude_layers : iterable of str
        Layer names whose variables should be dropped before learning, for
        instance to leave out a layer measured on only part of the cohort.
    use_smoothing : bool
        Laplace prior. Automatically on for BIC. Turn on elsewhere when
        rare state combinations trigger inference errors.
    within_layers, arcs_between_outcomes, selection_parents
        The three structural conventions. See `configure_guided_structure`;
        the defaults reproduce the behaviour that used to be fixed in code.
    forbidden_pairs, mandatory_pairs, no_parents, no_children
        Extra structural knowledge, as `(parent, child)` pairs and variable
        names. `vcibayes.spec` builds these from a spec's `constraints`
        block, and `vcibayes.analysis.Analysis` passes them in for you.

    Notes
    -----
    * When `enforce_structure=True`, `configure_guided_structure` restricts
      arcs to obey the layer order and any constraints given.
    * When `enforce_structure=False` every constraint is skipped, including
      the layer order. That is a genuinely unconstrained search, useful as a
      comparison but not as the analysis.
    * After learning, hard outcome→dropout arcs are added if not already
      present, so scenario inference always sees the dropout mechanism.
    """
    import pyagrum as gum
    random.seed(random_seed)
    np.random.seed(random_seed)

    exclude_layers = set(exclude_layers)
    layer_map_filtered = {k: v for k, v in layer_map.items() if k not in exclude_layers}
    excluded_vars = [v for k in exclude_layers for v in layer_map.get(k, [])]

    outcome_vars_all, dropout_vars_all = collect_outcome_vars(
        layer_map, outcome_patterns=outcome_patterns, dropout_patterns=dropout_patterns,
    )
    outcome_layer_vars = outcome_vars_all + dropout_vars_all
    drop_outcomes = [v for v in outcome_layer_vars if v not in outcomes]

    df_reduced = df.drop(columns=drop_outcomes + excluded_vars, errors="ignore")
    variables_to_keep = df_reduced.columns.tolist()

    template = fixed_template if fixed_template is not None \
        else type_processor.discretizedTemplate(df_reduced)

    learner = gum.BNLearner(df_reduced, template)

    score = score.upper()
    if score == "K2":
        learner.useScoreK2()
    elif score == "BIC":
        learner.useScoreBIC()
    elif score == "BDEU":
        learner.useScoreBDeu(ess=1)
    else:
        raise ValueError(f"Unsupported score {score!r}: choose K2, BIC, or BDeu")

    if use_smoothing or score == "BIC":
        learner.useSmoothingPrior()

    if use_tabu:
        learner.useLocalSearchWithTabuList()
    else:
        learner.useGreedyHillClimbing()

    if enforce_structure:
        dropout_vars, true_outcomes = configure_guided_structure(
            learner, layer_map_filtered, variables_to_keep, outcomes,
            dropout_patterns=dropout_patterns,
            within_layers=within_layers,
            arcs_between_outcomes=arcs_between_outcomes,
            selection_parents=selection_parents,
            forbidden_pairs=forbidden_pairs,
            mandatory_pairs=mandatory_pairs,
            no_parents=no_parents,
            no_children=no_children,
        )
    else:
        # Same pair `configure_guided_structure` would have returned, without
        # touching the learner. NB: `collect_outcome_vars` returns
        # (outcome_vars, dropout_vars) — the opposite order — so it must not be
        # unpacked into (dropout_vars, true_outcomes) directly.
        dropout_vars = [v for k in layer_map_filtered
                        if _match_any(k, dropout_patterns)
                        for v in layer_map_filtered[k]]
        true_outcomes = [v for v in outcomes if v not in dropout_vars]

    learner.setMaxIndegree(max_indegree)
    bn = learner.learnBN()

    if enforce_structure:
        try:
            dropout_ids = [bn.idFromName(n) for n in dropout_vars if n in bn.names()]
            outcome_ids = [bn.idFromName(n) for n in true_outcomes if n in bn.names()]
            for drop_id in dropout_ids:
                for out_id in outcome_ids:
                    if not bn.existsArc(out_id, drop_id):
                        bn.addArc(out_id, drop_id)
        except Exception:
            pass  # gum.InvalidArgument etc. — arc already exists / var missing
    return bn


def bootstrap_edge_frequencies(
    df: pd.DataFrame,
    *,
    outcomes: Sequence[str],
    layer_map: Mapping[str, Sequence[str]],
    type_processor: Any,
    build_bn_func: Callable[..., Any] = build_bn,
    n_bootstraps: int = 100,
    random_seed: int = 42,
    **build_kwargs: Any,
) -> dict[tuple[str, str], float]:
    """Fit `build_bn_func` on `n_bootstraps` resamples; return per-arc frequencies.

    Extra keyword arguments are forwarded to `build_bn_func` unchanged so
    callers can pin `score`, `use_smoothing`, `fixed_template`, etc.

    Notes
    -----
    The denominator is `n_bootstraps`, **not** the number of resamples that
    fitted successfully. A failed fit therefore lowers every frequency rather
    than being excluded from the calculation. These frequencies are reported
    as the `f=NN%` arc labels in published figures, so changing the
    denominator would silently restate them.
    """
    counts: dict[tuple[str, str], int] = defaultdict(int)
    successes = 0

    for i in range(n_bootstraps):
        seed = random_seed + i
        boot = df.sample(frac=1.0, replace=True, random_state=seed)
        try:
            bn = build_bn_func(
                boot, outcomes=outcomes, layer_map=layer_map,
                type_processor=type_processor, random_seed=seed, **build_kwargs,
            )
        except Exception as exc:
            print(f"Bootstrap {i} failed: {exc}")
            continue
        successes += 1
        for parent_id, child_id in bn.arcs():
            counts[(bn.variable(parent_id).name(), bn.variable(child_id).name())] += 1

    if successes < n_bootstraps:
        print(f"Note: {n_bootstraps - successes}/{n_bootstraps} bootstrap fits "
              "failed; frequencies are still divided by n_bootstraps.")
    return {edge: count / n_bootstraps for edge, count in counts.items()}


def bootstrap_scenario_risks(
    df: pd.DataFrame,
    *,
    scenario_profiles: Sequence[tuple[str, Mapping[str, Any]]],
    target_outcomes: Sequence[tuple[str, str]],
    build_bn_func: Callable[..., Any] = build_bn,
    layer_map: Mapping[str, Sequence[str]],
    type_processor: Any,
    outcomes_for_learning: Sequence[str],
    n_bootstraps: int = 200,
    random_seed: int = 42,
    **build_kwargs: Any,
) -> pd.DataFrame:
    """Compute posterior probabilities under a set of patient profiles.

    Parameters
    ----------
    scenario_profiles : sequence of (label, evidence_dict)
        Each dict maps a variable name to the evidence for it, passed to
        `LazyPropagation.setEvidence` unchanged. Prefer **state indices**:
        pyAgrum reads a bare integer as a state index, a numeric *string*
        as a value to place in a bin, and rejects an interval label such as
        `'(45;64.6['` outright. `vcibayes.analysis.Analysis.resolve_profile`
        converts any of these to indices and reports what it could not
        match; using it avoids the failure mode below.
    target_outcomes : sequence of (var_name, display_label)
    outcomes_for_learning : sequence of str
        Passed to `build_bn_func` as the fixed set of outcomes so bootstrap
        networks are structurally comparable across resamples.

    Notes
    -----
    Evidence that pyAgrum rejects raises `gum.InvalidArgument`, which this
    function catches and skips. The affected scenario then produces no rows
    at all rather than an error, so check that every profile you passed
    appears in the result.

    Pass `fixed_template` (via `**build_kwargs`) when the profiles refer to
    discretised variables. Without it every resample recomputes its own bin
    edges, and a fixed profile silently refers to a different group of
    people in each resample.
    """
    import pyagrum as gum

    samples: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    label_cache: dict[str, list[str]] = {}
    failed = 0

    for i in range(n_bootstraps):
        seed = random_seed + i
        boot = df.sample(frac=1.0, replace=True, random_state=seed)
        try:
            bn = build_bn_func(
                boot, outcomes=list(outcomes_for_learning), layer_map=layer_map,
                type_processor=type_processor, random_seed=seed, **build_kwargs,
            )
        except Exception:
            failed += 1
            continue

        for scenario_name, evidence in scenario_profiles:
            ie = gum.LazyPropagation(bn)
            try:
                ie.setEvidence(dict(evidence))
            except gum.InvalidArgument:
                continue
            for outcome_name, _ in target_outcomes:
                if outcome_name not in label_cache:
                    label_cache[outcome_name] = list(
                        bn.variable(bn.idFromName(outcome_name)).labels()
                    )
                posterior = ie.posterior(outcome_name)
                for idx, state in enumerate(label_cache[outcome_name]):
                    samples[(scenario_name, outcome_name, state)].append(float(posterior[idx]))

    outcome_labels = dict(target_outcomes)
    rows = []
    for (scenario_name, outcome_name, state), values in samples.items():
        arr = np.asarray(values, float)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            continue
        rows.append({
            "Scenario": scenario_name,
            "Outcome": outcome_labels.get(outcome_name, outcome_name),
            "Category": state,
            "Mean probability": arr.mean(),
            "Std": arr.std(ddof=1) if arr.size > 1 else 0.0,
            "CI 2.5%": np.quantile(arr, 0.025),
            "CI 97.5%": np.quantile(arr, 0.975),
            "Bootstraps": int(arr.size),
        })
    if failed:
        print(f"Warning: {failed}/{n_bootstraps} bootstrap fits failed and were skipped.")
    return pd.DataFrame(rows).sort_values(["Scenario", "Outcome", "Category"]).reset_index(drop=True)


def descendants(bn: Any, start_id: int) -> set[int]:
    """All nodes reachable from `start_id` by following directed arcs."""
    seen: set[int] = set()
    stack = [start_id]
    while stack:
        for child in bn.children(stack.pop()):
            if child not in seen:
                seen.add(child)
                stack.append(child)
    return seen


def bootstrap_knob_sweep(
    df: pd.DataFrame,
    *,
    base_profile: Mapping[str, Any],
    knob: str,
    outcomes: Sequence[str],
    outcomes_for_learning: Sequence[str],
    layer_map: Mapping[str, Sequence[str]],
    type_processor: Any,
    build_bn_func: Callable[..., Any] = build_bn,
    n_bootstraps: int = 200,
    random_seed: int = 42,
    verbose: bool = True,
    **build_kwargs: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Sensitivity sweep: fix a patient, vary one variable across its states.

    Returns `(sweep_df, meta)` where `sweep_df` has one row per
    (outcome, knob state, outcome state) with bootstrap mean and 95% CI.
    `meta` carries the resolved knob states and outcome states.

    Notes
    -----
    Warns if any variable in `base_profile` lies on a directed path from
    `knob` to an outcome (overadjustment / blocked mediator). Uses a fixed
    discretisation template so knob states mean the same thing across
    resamples.
    """
    import pyagrum as gum

    fixed_template = type_processor.discretizedTemplate(
        _reduced_for_template(
            df, layer_map, outcomes_for_learning,
            build_kwargs.get("exclude_layers", ()),
            outcome_patterns=build_kwargs.get(
                "outcome_patterns", DEFAULT_OUTCOME_LAYER_PATTERNS),
            dropout_patterns=build_kwargs.get(
                "dropout_patterns", DEFAULT_DROPOUT_LAYER_PATTERNS),
        )
    )
    build_kwargs = {**build_kwargs, "fixed_template": fixed_template, "use_smoothing": True}

    ref_bn = build_bn_func(
        df, outcomes=list(outcomes_for_learning), layer_map=layer_map,
        type_processor=type_processor, random_seed=random_seed, **build_kwargs,
    )

    def labels_of(name: str) -> list[str]:
        return list(ref_bn.variable(ref_bn.idFromName(name)).labels())

    if knob in base_profile:
        raise ValueError("base_profile must not contain the knob variable.")

    applied, rejected, snapped = {}, {}, {}
    for var, val in base_profile.items():
        if var not in ref_bn.names():
            rejected[var] = val
            continue
        state = state_for_value(labels_of(var), val)
        if state is None:
            rejected[var] = val
        else:
            applied[var] = state
            if str(val) != state:
                snapped[var] = f"{val} -> {state!r}"

    if verbose:
        print("Fixed patient — evidence applied:", applied or "(none)")
        if snapped:
            print("Fixed patient — snapped to bin:", snapped)
        if rejected:
            print("Fixed patient — REJECTED:", rejected,
                  "(unknown variable or value not matchable — check the discretised template).")

    knob_descendants = {
        ref_bn.variable(i).name()
        for i in descendants(ref_bn, ref_bn.idFromName(knob))
    }
    blocked = [v for v in applied if v in knob_descendants]
    if blocked and verbose:
        print(f"WARNING: base_profile fixes {blocked}, which lie downstream of "
              f"{knob!r}. Holding a mediator constant blocks part of the knob's "
              "effect on the outcomes.")

    applied_idx = {v: labels_of(v).index(s) for v, s in applied.items()}
    knob_states = labels_of(knob)
    outcome_states = {o: labels_of(o) for o in outcomes}

    samples: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    failed = 0
    for i in range(n_bootstraps):
        seed = random_seed + i
        boot = df.sample(frac=1.0, replace=True, random_state=seed)
        try:
            bn = build_bn_func(
                boot, outcomes=list(outcomes_for_learning), layer_map=layer_map,
                type_processor=type_processor, random_seed=seed, **build_kwargs,
            )
        except Exception:
            failed += 1
            continue
        for k_idx, k_state in enumerate(knob_states):
            try:
                ie = gum.LazyPropagation(bn)
                ie.setEvidence({**applied_idx, knob: k_idx})
                post = {o: ie.posterior(o) for o in outcomes}
            except Exception:
                continue
            for outcome in outcomes:
                for s_idx, s_label in enumerate(outcome_states[outcome]):
                    samples[(outcome, k_state, s_label)].append(float(post[outcome][s_idx]))

    rows = []
    for (outcome, k_state, s_label), values in samples.items():
        arr = np.asarray(values, float)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            continue
        rows.append({
            "Outcome": outcome,
            knob: k_state,
            "Outcome state": s_label,
            "P": arr.mean(),
            "CI_low": np.quantile(arr, 0.025),
            "CI_high": np.quantile(arr, 0.975),
            "Bootstraps": int(arr.size),
        })
    if verbose and failed:
        print(f"Note: {failed}/{n_bootstraps} bootstrap fits failed and were skipped.")
    if not rows:
        raise RuntimeError("No valid scenarios were produced — check base_profile.")

    return pd.DataFrame(rows), {
        "knob": knob, "knob_states": knob_states,
        "outcomes": list(outcomes), "outcome_states": outcome_states,
    }


def _reduced_for_template(
    df: pd.DataFrame,
    layer_map: Mapping[str, Sequence[str]],
    outcomes_for_learning: Sequence[str],
    exclude_layers: Iterable[str],
    *,
    outcome_patterns: Sequence[str] = DEFAULT_OUTCOME_LAYER_PATTERNS,
    dropout_patterns: Sequence[str] = DEFAULT_DROPOUT_LAYER_PATTERNS,
) -> pd.DataFrame:
    """Reproduce `build_bn`'s column reduction so one template covers all bootstraps.

    The patterns must be the same ones `build_bn` will be called with. If they
    are not, this function and `build_bn` disagree about which columns are
    outcomes, the template ends up describing a different set of variables
    than the learner is given, and `BNLearner` raises.
    """
    excluded = [v for k in exclude_layers for v in layer_map.get(k, [])]
    outcome_all, dropout_all = collect_outcome_vars(
        layer_map, outcome_patterns=outcome_patterns, dropout_patterns=dropout_patterns,
    )
    drop_outcomes = [v for v in outcome_all + dropout_all if v not in outcomes_for_learning]
    return df.drop(columns=drop_outcomes + excluded, errors="ignore")
