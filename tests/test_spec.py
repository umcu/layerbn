"""Spec loading and validation.

Validation is the package's main promise to a user who does not read Python:
that a mistake in `spec.yml` is reported by key, immediately, instead of
surfacing forty minutes into a bootstrap. These tests hold it to that.
"""
from __future__ import annotations

import pytest

from layerbn.spec import SpecError, check_against_dataframe, load_spec

from .conftest import MINIMAL_SPEC

# --------------------------------------------------------------------------
# the shipped template
# --------------------------------------------------------------------------

def test_template_spec_loads(spec):
    """The template every project starts from must be valid."""
    assert spec.name == "my-study"
    assert len(spec.layers) == 7
    assert spec.model.seed == 42


def test_template_declares_the_variant_the_notebook_uses(spec):
    """The notebook hard-codes VARIANT="joint" and an ablation variant."""
    names = [v.name for v in spec.variants]
    assert "joint" in names
    assert "with_markers" in names


def test_layer_order_is_file_order(spec):
    """The ordering is the constraint, so it must survive loading intact."""
    assert spec.layer_order[0].startswith("L0")
    assert spec.layer_order[-1].startswith("L6")
    assert spec.layer_index("AGE") < spec.layer_index("OUTCOME DECLINE")


def test_roles_are_picked_up(spec):
    assert spec.layers_with_role("outcome") == ["L5 – Outcomes"]
    assert spec.layers_with_role("selection") == ["L6 – Dropout"]


# --------------------------------------------------------------------------
# errors name the offending key
# --------------------------------------------------------------------------

def test_missing_file_is_reported(tmp_path):
    with pytest.raises(SpecError, match="not found"):
        load_spec(tmp_path / "nope.yml")


def test_variable_in_two_layers_is_rejected(write_spec):
    text = MINIMAL_SPEC.replace("variables: [MEASUREMENT A]", "variables: [AGE]")
    with pytest.raises(SpecError, match="AGE"):
        load_spec(write_spec(text))


def test_duplicate_layer_names_are_rejected(write_spec):
    text = MINIMAL_SPEC.replace('"L1 - Measurements"', '"L0 - Demographics"')
    with pytest.raises(SpecError):
        load_spec(write_spec(text))


def test_spec_without_an_outcome_layer_is_rejected(write_spec):
    text = MINIMAL_SPEC.replace("role: outcome", "role: covariate")
    with pytest.raises(SpecError, match="outcome"):
        load_spec(write_spec(text))


def test_unknown_variant_is_reported_with_suggestion(spec):
    with pytest.raises(SpecError) as excinfo:
        spec.variant("jont")
    assert "joint" in str(excinfo.value)


def test_unknown_excluded_layer_is_rejected(write_spec):
    text = MINIMAL_SPEC.replace("exclude_layers: []", 'exclude_layers: ["L9 - Nope"]')
    with pytest.raises(SpecError, match="L9 - Nope"):
        load_spec(write_spec(text))


# --------------------------------------------------------------------------
# constraints may only narrow
# --------------------------------------------------------------------------

def test_requiring_an_upstream_arc_is_rejected(write_spec):
    """The headline guarantee: constraints cannot license an upstream arc."""
    text = MINIMAL_SPEC + """
constraints:
  require:
    - {from: OUTCOME EVENT, to: AGE}
"""
    with pytest.raises(SpecError) as excinfo:
        load_spec(write_spec(text))
    message = str(excinfo.value)
    assert "OUTCOME EVENT" in message and "AGE" in message
    assert "Reorder" in message or "narrow" in message


def test_arc_both_required_and_forbidden_is_rejected(write_spec):
    text = MINIMAL_SPEC + """
constraints:
  forbid:
    - {from: AGE, to: OUTCOME EVENT}
  require:
    - {from: AGE, to: OUTCOME EVENT}
"""
    with pytest.raises(SpecError):
        load_spec(write_spec(text))


def test_downstream_constraints_are_accepted(write_spec):
    text = MINIMAL_SPEC + """
constraints:
  forbid:
    - {from: AGE, to: SEX}
  require:
    - {from: SEX, to: OUTCOME EVENT}
  no_parents: [AGE]
  no_children: [OUTCOME EVENT]
  within_layers: false
"""
    loaded = load_spec(write_spec(text))
    assert ("SEX", "OUTCOME EVENT") in loaded.mandatory_pairs
    assert ("AGE", "SEX") in loaded.forbidden_pairs
    assert loaded.constraints.within_layers is False


def test_layer_ended_rule_expands_to_every_pair(write_spec):
    """One layer-to-layer rule must stand for every arc between them."""
    text = MINIMAL_SPEC + """
constraints:
  forbid:
    - {from_layer: "L0 - Demographics", to_layer: "L2 - Outcomes"}
"""
    loaded = load_spec(write_spec(text))
    assert ("AGE", "OUTCOME EVENT") in loaded.forbidden_pairs
    assert ("SEX", "OUTCOME EVENT") in loaded.forbidden_pairs


def test_constraints_default_to_the_documented_conventions(spec):
    """A spec with no constraints block behaves as the README describes."""
    assert spec.constraints.within_layers is True
    assert spec.constraints.arcs_between_outcomes is False
    assert spec.constraints.selection_parents == "outcomes"


# --------------------------------------------------------------------------
# spec versus data
# --------------------------------------------------------------------------

def test_check_against_dataframe_is_quiet_when_they_agree(spec, demo_df):
    assert check_against_dataframe(spec, demo_df.columns) == []


def test_check_against_dataframe_reports_a_missing_column(spec, demo_df):
    warnings = check_against_dataframe(spec, [c for c in demo_df.columns if c != "AGE"])
    assert any("AGE" in w for w in warnings)
