"""The structural guarantees, checked on networks that were actually learned.

`test_spec.py` checks that a bad spec is rejected. These tests check the
claim the package exists to make: that no arc in a learned network runs
against the declared layer order, whatever the data say.
"""
from __future__ import annotations

import pytest

from layerbn.analysis import Analysis


@pytest.fixture(scope="module")
def study(request):
    """One Analysis over the template spec and the demo cohort."""
    import shutil
    from pathlib import Path
    from tempfile import mkdtemp

    from layerbn.demo import make_demo_cohort
    from layerbn.spec import load_spec

    templates = Path(__file__).resolve().parents[1] / "layerbn" / "templates"
    workdir = Path(mkdtemp())
    request.addfinalizer(lambda: shutil.rmtree(workdir, ignore_errors=True))
    shutil.copyfile(templates / "spec.yml", workdir / "spec.yml")

    spec = load_spec(workdir / "spec.yml")
    return Analysis(spec, make_demo_cohort(n=600, seed=0), verbose=False)


def arcs_by_name(bn):
    return [(bn.variable(p).name(), bn.variable(c).name()) for p, c in bn.arcs()]


# --------------------------------------------------------------------------
# the layer ordering
# --------------------------------------------------------------------------

def test_no_arc_runs_upstream(study):
    """The central guarantee. An arc may go down the layer list, never up."""
    bn = study.network("joint")
    for parent, child in arcs_by_name(bn):
        assert study.spec.layer_index(parent) <= study.spec.layer_index(child), (
            f"{parent} -> {child} runs upstream, from layer "
            f"{study.spec.layer_index(parent)} to {study.spec.layer_index(child)}"
        )


def test_no_arcs_between_outcomes(study):
    """One endpoint must never be reported as a cause of another."""
    bn = study.network("joint")
    outcomes = set(study.spec.layers[5].variables)
    for parent, child in arcs_by_name(bn):
        assert not (parent in outcomes and child in outcomes)


def test_dropout_is_downstream_of_every_outcome(study):
    """Selection layer: every outcome connects to it after learning."""
    bn = study.network("joint")
    arcs = set(arcs_by_name(bn))
    dropout = "DROPOUT REASON"
    for outcome in ("OUTCOME DECLINE", "OUTCOME EVENT"):
        assert (outcome, dropout) in arcs


def test_only_outcomes_point_into_the_selection_layer(study):
    bn = study.network("joint")
    outcomes = set(study.spec.layers[5].variables)
    for parent, child in arcs_by_name(bn):
        if child == "DROPOUT REASON":
            assert parent in outcomes, f"{parent} should not point at dropout"


def test_excluded_layer_is_absent_from_the_network(study):
    """`exclude_layers` on a variant drops those variables entirely."""
    bn = study.network("joint")
    assert "MARKER 1" not in bn.names()
    assert "MARKER 2" not in bn.names()


def test_ablation_variant_puts_the_layer_back(study):
    bn = study.network("with_markers")
    assert "MARKER 1" in bn.names()


# --------------------------------------------------------------------------
# reproducibility
# --------------------------------------------------------------------------

def test_the_same_seed_gives_the_same_network(study):
    """A published seed has to mean something."""
    first = sorted(arcs_by_name(study.network("joint")))
    second = sorted(arcs_by_name(study.network("joint", refresh=True)))
    assert first == second


def test_the_demo_cohort_is_reproducible():
    from layerbn.demo import make_demo_cohort

    a = make_demo_cohort(n=200, seed=7)
    b = make_demo_cohort(n=200, seed=7)
    assert a.equals(b)
    assert not a.equals(make_demo_cohort(n=200, seed=8))


def test_bootstrap_frequencies_are_reproducible(study):
    first = study.edge_frequencies("joint", refresh=True)
    second = study.edge_frequencies("joint", refresh=True)
    assert first == second


# --------------------------------------------------------------------------
# constraints reach the learner
# --------------------------------------------------------------------------

def test_a_forbidden_arc_is_absent_from_the_learned_network(study):
    """Forbidding an arc the learner would otherwise draw must remove it."""
    baseline = set(arcs_by_name(study.network("joint")))
    # Sorted, so the arc under test does not depend on set iteration order.
    candidate = next(
        ((p, c) for p, c in sorted(baseline)
         if study.spec.layer_index(p) < study.spec.layer_index(c)),
        None,
    )
    assert candidate is not None, "expected the demo network to have a downstream arc"

    bn = study.network("joint", forbidden_pairs={candidate})
    assert candidate not in set(arcs_by_name(bn))


def test_forbidding_an_outcome_to_dropout_arc_is_honoured(study):
    """Those arcs are re-added after learning; an explicit forbid still wins.

    Otherwise `constraints.forbid` would be silently ignored for exactly the
    arcs the selection layer exists to model, and the spec's "constraints
    only narrow" promise would not hold.
    """
    pair = ("OUTCOME EVENT", "DROPOUT REASON")
    assert pair in set(arcs_by_name(study.network("joint")))

    bn = study.network("joint", forbidden_pairs={pair})
    assert pair not in set(arcs_by_name(bn))
    # The other outcome is untouched.
    assert ("OUTCOME DECLINE", "DROPOUT REASON") in set(arcs_by_name(bn))


def test_a_required_arc_is_present_in_the_learned_network(study):
    bn = study.network("joint", mandatory_pairs={("SEX", "OUTCOME EVENT")})
    assert ("SEX", "OUTCOME EVENT") in set(arcs_by_name(bn))


def test_no_parents_pins_a_root(study):
    bn = study.network("joint", no_parents={"EDUCATION YEARS"})
    for _parent, child in arcs_by_name(bn):
        assert child != "EDUCATION YEARS"


def test_within_layers_false_disconnects_a_layer(study):
    bn = study.network("joint", within_layers=False)
    for parent, child in arcs_by_name(bn):
        assert study.spec.layer_index(parent) != study.spec.layer_index(child)


# --------------------------------------------------------------------------
# results are well formed
# --------------------------------------------------------------------------

def test_bins_cover_every_variable_in_the_network(study):
    bins = study.bins("joint")
    assert not bins.empty
    assert len(bins) == len(study.network("joint").names())


def test_information_is_non_negative_and_covers_the_targets(study):
    info = study.information("joint")
    assert set(info["Target"]) == {"OUTCOME DECLINE", "OUTCOME EVENT"}
    assert (info["MI"] >= 0).all()
    assert info["CMI"].dropna().ge(0).all()


def test_stable_edges_frequencies_are_probabilities(study):
    edges = study.stable_edges("joint")
    assert not edges.empty
    assert edges["Frequency"].between(0, 1).all()
    assert set(edges.columns) == {"Parent", "Child", "Frequency", "In network"}


def test_scenario_probabilities_sum_to_one_per_outcome(study):
    risks = study.scenarios("joint")
    assert not risks.isna().any().any()
    totals = risks.groupby(["Scenario", "Outcome"])["Mean probability"].sum()
    assert totals.between(0.99, 1.01).all()


def test_knob_sweep_returns_a_finite_table(study):
    sweep, meta = study.knob_sweep("joint")
    assert not sweep.isna().any().any()
    assert sweep["P"].between(0, 1).all()
    assert meta["knob"] == "MEASUREMENT A"
