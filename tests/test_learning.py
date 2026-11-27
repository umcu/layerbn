"""Structure learning: the layer guarantee, the rules, and recovery of a known structure."""
from __future__ import annotations

import pytest

from layerbn.bn_utils import (
    bootstrap_edge_frequencies,
    build_bn,
    configure_structure,
    descendants,
)
from layerbn.demo import TRUE_EDGES, make_demo_cohort
from layerbn.discretisation import make_type_processor


@pytest.fixture(scope="module")
def layer_map(project):
    return {k: list(v) for k, v in project.network("all_variables").layer_map.items()}


@pytest.fixture(scope="module")
def processor():
    return make_type_processor(method="quantile", bins=4, categorical_max_levels=10)


def arcs_of(bn):
    return {(bn.variable(p).name(), bn.variable(c).name()) for p, c in bn.arcs()}


def layer_index(layer_map):
    return {c: i for i, members in enumerate(layer_map.values()) for c in members}


# -- the guarantee the package exists for ---------------------------------------------

def test_no_arc_runs_against_the_layer_order(demo_df, layer_map, processor):
    bn = build_bn(demo_df, layer_map, processor)
    position = layer_index(layer_map)
    assert arcs_of(bn), "the demo should yield some arcs"
    for parent, child in arcs_of(bn):
        assert position[parent] <= position[child], f"{parent} -> {child} runs upstream"


def test_the_guarantee_holds_in_every_bootstrap_resample(demo_df, layer_map, processor):
    freqs, failed = bootstrap_edge_frequencies(
        demo_df, layer_map=layer_map, type_processor=processor, resamples=8, seed=1)
    position = layer_index(layer_map)
    assert failed == 0 and freqs
    assert all(position[p] <= position[c] for p, c in freqs)


def test_reordering_the_layers_changes_what_is_possible(demo_df, layer_map, processor):
    """The order is the constraint: reverse it and the arcs reverse with it."""
    forward = arcs_of(build_bn(demo_df, layer_map, processor))
    backward_map = dict(reversed(list(layer_map.items())))
    backward = arcs_of(build_bn(demo_df, backward_map, processor))
    position = layer_index(backward_map)
    assert all(position[p] <= position[c] for p, c in backward)
    assert forward != backward


def test_the_demo_structure_is_recovered(layer_map, processor):
    """With 800 participants the learner finds most known arcs and few wrong ones."""
    df = make_demo_cohort(n=800, seed=0)
    learned = arcs_of(build_bn(df, layer_map, processor))
    truth = set(TRUE_EDGES)
    recall = len(learned & truth) / len(truth)
    precision = len(learned & truth) / len(learned)
    assert recall >= 0.70, f"only {recall:.0%} of the true arcs were found"
    assert precision >= 0.80, f"only {precision:.0%} of the learned arcs are true"


# -- rules -------------------------------------------------------------------------------

def test_arcs_inside_a_layer_can_be_switched_off(demo_df, layer_map, processor):
    with_inner = arcs_of(build_bn(demo_df, layer_map, processor))
    layer = "Baseline measures"
    members = set(layer_map[layer])
    assert any(p in members and c in members for p, c in with_inner), \
        "this check needs an arc inside the layer to start from"
    without = arcs_of(build_bn(demo_df, layer_map, processor, no_inner_arcs=[layer]))
    assert not any(p in members and c in members for p, c in without)


def test_a_forbidden_arc_does_not_occur(demo_df, layer_map, processor):
    learned = arcs_of(build_bn(demo_df, layer_map, processor))
    victim = next(iter(learned))
    again = arcs_of(build_bn(demo_df, layer_map, processor, forbidden_pairs=[victim]))
    assert victim not in again


def test_a_required_arc_occurs(demo_df, layer_map, processor):
    pair = ("SEX", "OUTCOME")
    assert pair not in arcs_of(build_bn(demo_df, layer_map, processor))
    assert pair in arcs_of(build_bn(demo_df, layer_map, processor, mandatory_pairs=[pair]))


def test_no_parents_and_no_children(demo_df, layer_map, processor):
    bn = build_bn(demo_df, layer_map, processor,
                  no_parents=["EXPOSURE_A"], no_children=["AGE"])
    arcs = arcs_of(bn)
    assert not any(c == "EXPOSURE_A" for _, c in arcs)
    assert not any(p == "AGE" for p, _ in arcs)


def test_a_rule_naming_a_variable_outside_the_network_is_ignored(demo_df, layer_map, processor):
    build_bn(demo_df, layer_map, processor, mandatory_pairs=[("AGE", "NOT_IN_NETWORK")],
             no_parents=["NOT_IN_NETWORK"])


def test_a_pair_that_is_required_and_forbidden_is_named(layer_map):
    class Learner:
        def __getattr__(self, name):
            return lambda *a, **k: None
    with pytest.raises(ValueError, match=r"both required and forbidden.*AGE.*SEX"):
        configure_structure(Learner(), layer_map, forbidden_pairs=[("AGE", "SEX")],
                            mandatory_pairs=[("AGE", "SEX")])


def test_without_structure_enforced_arcs_may_run_upstream(demo_df, layer_map, processor):
    """The unconstrained search is only a comparison, but it must really be unconstrained."""
    bn = build_bn(demo_df, layer_map, processor, enforce_structure=False)
    position = layer_index(layer_map)
    assert any(position[p] > position[c] for p, c in arcs_of(bn))


@pytest.mark.parametrize("score", ["K2", "BIC", "BDeu"])
@pytest.mark.parametrize("search", ["tabu", "greedy"])
def test_every_score_and_search_runs(demo_df, layer_map, processor, score, search):
    bn = build_bn(demo_df, layer_map, processor, score=score, search=search)
    assert len(bn.names()) == len(layer_index(layer_map))


def test_the_maximum_number_of_parents_is_respected(demo_df, layer_map, processor):
    bn = build_bn(demo_df, layer_map, processor, max_parents=1)
    assert all(len(bn.parents(i)) <= 1 for i in bn.nodes())


def test_an_unknown_score_is_refused(demo_df, layer_map, processor):
    with pytest.raises(ValueError, match="Unsupported score"):
        build_bn(demo_df, layer_map, processor, score="AIC")


def test_the_same_seed_gives_the_same_network(demo_df, layer_map, processor):
    first = arcs_of(build_bn(demo_df, layer_map, processor, seed=3))
    second = arcs_of(build_bn(demo_df, layer_map, processor, seed=3))
    assert first == second


@pytest.mark.parametrize("score", ["K2", "BDeu"])
def test_smoothing_is_not_stacked_on_a_score_with_its_own_prior(
        demo_df, layer_map, processor, capfd, score):
    """aGrUM warns once per fit if a second prior is added to K2 or BDeu."""
    build_bn(demo_df, layer_map, processor, score=score)
    captured = capfd.readouterr()
    assert "implicit" not in captured.out + captured.err


# -- bootstrap frequencies ---------------------------------------------------------------

def test_frequencies_are_divided_by_the_resamples_requested(
        demo_df, layer_map, processor, monkeypatch):
    """A failed fit must lower every frequency, not drop out of the denominator."""
    import layerbn.bn_utils as module
    real = module.build_bn
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] % 2 == 0:
            raise RuntimeError("simulated failure")
        return real(*args, **kwargs)

    monkeypatch.setattr(module, "build_bn", flaky)
    freqs, failed = bootstrap_edge_frequencies(
        demo_df, layer_map=layer_map, type_processor=processor, resamples=6, seed=0)
    assert failed == 3
    assert max(freqs.values()) <= 0.5


def test_progress_is_reported_once_per_resample(demo_df, layer_map, processor):
    ticks = []
    bootstrap_edge_frequencies(demo_df, layer_map=layer_map, type_processor=processor,
                               resamples=3, seed=0, progress=lambda: ticks.append(1))
    assert len(ticks) == 3


def test_descendants_follow_arcs_downstream(demo_df, layer_map, processor):
    bn = build_bn(demo_df, layer_map, processor)
    ids = {bn.variable(i).name(): i for i in bn.nodes()}
    below = {bn.variable(i).name() for i in descendants(bn, ids["AGE"])}
    position = layer_index(layer_map)
    assert below and all(position[c] >= position["AGE"] for c in below)
    assert "AGE" not in below
