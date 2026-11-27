"""settings.yml and its checks against the design."""
from __future__ import annotations

import pytest

from layerbn.project import ProjectError
from layerbn.settings import SettingsError, load_settings, parse_settings


def parse(text: str):
    import yaml
    return parse_settings(yaml.safe_load(text))


# -- the settings file on its own -------------------------------------------------

def test_an_empty_file_gives_the_defaults():
    s = parse("settings_version: 3")
    assert (s.learning.score, s.learning.search, s.learning.max_parents) == ("K2", "tabu", 5)
    assert s.discretisation.bins == 4 and s.resamples == 200
    assert s.constraints.within_layers is True
    assert [n.name for n in s.networks] == ["main"]


def test_an_unknown_setting_is_reported_with_a_suggestion():
    with pytest.raises(SettingsError,
                       match=r"bootstrap.resample: unknown.*Did you mean 'resamples'"):
        parse("bootstrap:\n  resample: 5")
    with pytest.raises(SettingsError, match="learning.max_parent: unknown"):
        parse("learning:\n  max_parent: 3")


def test_a_wrong_value_names_the_allowed_ones():
    with pytest.raises(SettingsError, match=r"learning.score: 'K3'.*K2.*BIC.*BDeu"):
        parse("learning:\n  score: K3")
    with pytest.raises(SettingsError, match="bootstrap.resamples: must be at least 1"):
        parse("bootstrap:\n  resamples: 0")
    with pytest.raises(SettingsError, match="expected true or false"):
        parse("constraints:\n  within_layers: maybe")


def test_a_version_2_spec_points_to_migrate():
    with pytest.raises(SettingsError, match="layerbn migrate"):
        parse("spec_version: 2\nlayers: []")
    with pytest.raises(SettingsError, match="version 2 spec"):
        parse("layers:\n  - name: A\n    variables: [X]\nvariants: []")


def test_the_score_is_case_insensitive():
    assert parse("learning:\n  score: bdeu").learning.score == "BDEU"


def test_network_names_must_be_unique():
    with pytest.raises(SettingsError, match="already used"):
        parse("networks:\n  - name: a\n  - name: a")


def test_an_arc_rule_needs_both_ends():
    with pytest.raises(SettingsError, match="one of 'to' or 'to_layer' is missing"):
        parse("constraints:\n  forbid:\n    - {from: A}")
    with pytest.raises(SettingsError, match="either 'from' or 'from_layer'"):
        parse("constraints:\n  forbid:\n    - {from: A, from_layer: B, to: C}")


def test_a_missing_file_is_reported(tmp_path):
    with pytest.raises(SettingsError, match="not found"):
        load_settings(tmp_path / "settings.yml")


def test_the_example_settings_load(settings_path):
    s = load_settings(settings_path)
    assert s.name and s.data.file == "data/demo_cohort.csv"


# -- settings checked against the design -----------------------------------------

def test_names_may_be_columns_or_labels(make_project):
    p = make_project("""
constraints:
  forbid:
    - {from: AGE, to: "Exposure A (score)"}
    - {from_layer: Baseline measures, to_layer: Background}
""")
    assert ("AGE", "EXPOSURE_A") in p.forbidden_pairs
    # A layer name stands for every variable in it.
    assert ("MEASURE_2", "SEX") in p.forbidden_pairs


def test_an_unknown_variable_in_a_rule_is_reported(make_project):
    with pytest.raises(
            Exception, match=r"constraints.forbid\[0\].from.*'AGEE'.*Did you mean 'AGE'"):
        make_project("constraints:\n  forbid:\n    - {from: AGEE, to: SEX}")


def test_a_required_arc_against_the_layer_order_is_refused(make_project):
    with pytest.raises(ProjectError, match="runs against the layer order"):
        make_project("constraints:\n  require:\n    - {from: OUTCOME, to: AGE}")


def test_a_required_arc_must_not_be_forbidden(make_project):
    with pytest.raises(ProjectError, match="both required and forbidden"):
        make_project("""
constraints:
  forbid: [{from: AGE, to: EXPOSURE_A}]
  require: [{from: AGE, to: EXPOSURE_A}]
""")


def test_a_broad_layer_rule_can_collide_with_a_required_arc(make_project):
    with pytest.raises(ProjectError, match="both required and forbidden"):
        make_project("""
constraints:
  forbid: [{from_layer: Background, to_layer: Exposures}]
  require: [{from: SEX, to: EXPOSURE_A}]
""")


def test_a_required_arc_inside_a_layer_without_inner_arcs_is_refused(
        make_project, write_tables):
    write_tables("variable,layer\nA,X\nB,X\nC,Y", "layer,arcs_within\nX,no\nY,")
    with pytest.raises(ProjectError, match="arcs_within set to no"):
        make_project("""
data: {variables_file: variables.csv}
constraints:
  require: [{from: A, to: B}]
""")


def test_arcs_within_a_layer_follow_the_layer_setting_or_the_default(
        make_project, write_tables):
    write_tables("variable,layer\nA,X\nB,X\nC,Y", "layer,arcs_within\nX,no\nY,")
    p = make_project("data: {variables_file: variables.csv}")
    assert p.layers_without_inner_arcs == {"X"}
    p = make_project("data: {variables_file: variables.csv}\n"
                     "constraints: {within_layers: false}")
    assert p.layers_without_inner_arcs == {"X", "Y"}


def test_a_variable_cannot_be_both_root_and_sink(make_project):
    with pytest.raises(ProjectError, match="no_parents and no_children"):
        make_project("constraints:\n  no_parents: [AGE]\n  no_children: [AGE]")


def test_a_required_arc_to_a_variable_without_parents_is_refused(make_project):
    with pytest.raises(ProjectError, match="no_parents"):
        make_project("""
constraints:
  no_parents: [EXPOSURE_A]
  require: [{from: AGE, to: EXPOSURE_A}]
""")


def test_networks_exclude_layers_and_variables(make_project):
    p = make_project("""
networks:
  - name: full
  - name: reduced
    exclude_layers: [Exposures]
    exclude_variables: [SEX]
""")
    full, reduced = p.network("full"), p.network("reduced")
    assert len(full.columns) == 8 and len(reduced.columns) == 8 - 2 - 1
    assert "Exposures" not in reduced.layer_map
    assert "SEX" not in reduced.columns
    # Layer order is kept.
    assert list(reduced.layer_map)[0] == "Background"


def test_a_network_needs_at_least_two_variables(make_project):
    with pytest.raises(ProjectError, match="at least two"):
        make_project("""
networks:
  - name: tiny
    exclude_layers: [Background, Exposures, Baseline measures]
""")


def test_an_unknown_network_is_reported(project):
    with pytest.raises(ProjectError, match="no network named 'nope'"):
        project.network("nope")


def test_analyses_must_point_at_an_existing_network(make_project):
    with pytest.raises(ProjectError, match="analyses.profiles.network.*'other'"):
        make_project("""
networks: [{name: a}]
analyses:
  profiles:
    network: other
    groups: {"g": {AGE: 70}}
""")


def test_the_variable_moved_in_a_sweep_cannot_be_held_fixed(make_project):
    with pytest.raises(ProjectError, match="cannot also be held fixed"):
        make_project("""
analyses:
  sweep:
    variable: EXPOSURE_A
    fixed: {EXPOSURE_A: 50}
""")


def test_targets_default_to_the_marked_variables(project):
    targets = project.default_targets(project.network())
    assert set(targets) == {"OUTCOME"}


def test_without_marked_targets_the_last_layer_is_used(make_project, write_tables):
    write_tables("variable,layer\nA,X\nB,Y\nC,Y")
    p = make_project("data: {variables_file: variables.csv}")
    assert p.default_targets(p.network()) == ("B", "C")


def test_with_resamples_overrides_every_count(make_project):
    p = make_project("""
bootstrap: {resamples: 100}
networks: [{name: a, resamples: 50}]
analyses:
  profiles: {resamples: 80, groups: {"g": {AGE: 70}}}
""").with_resamples(7)
    assert p.network("a").resamples == 7 and p.settings.profiles.resamples is None


def test_the_summary_lists_layers_in_order(project):
    text = project.summary()
    assert text.index("Background") < text.index("Exposures") < text.index("Outcome")
    assert "no arcs inside this layer" in text
