"""Converting a version 2 spec."""
from __future__ import annotations

import pytest
import yaml

from layerbn.__main__ import main
from layerbn.migrate import MigrationError, convert, migrate
from layerbn.project import load_project

V2 = """
spec_version: 2
name: old-study
description: An analysis written for version 2.
data:
  path: cohort.parquet
layers:
  - name: "L0 - Demographics"
    role: covariate
    variables: [AGE, SEX]
  - name: "L1 - Measurements"
    role: covariate
    variables: [MARKER, SCORE]
  - name: "L2 - Outcomes"
    role: outcome
    variables: [DECLINE, EVENT]
  - name: "L3 - Dropout"
    role: selection
    variables: [DROPOUT]
constraints:
  forbid:
    - {from: AGE, to: SEX}
  no_parents: [AGE]
discretisation: {method: quantile, n_bins: 3, threshold: 8}
model: {score: BIC, use_tabu: false, max_indegree: 4, seed: 7}
bootstrap: {n: 50}
variants:
  - name: decline
    outcomes: [DECLINE, DROPOUT]
    exclude_layers: []
  - name: joint
    outcomes: [DECLINE, EVENT, DROPOUT]
    exclude_layers: ["L1 - Measurements"]
    bootstrap_n: 10
analyses:
  information:
    targets: [DECLINE]
  scenarios:
    bootstrap_n: 20
    profiles:
      "Older": {AGE: 80}
    targets:
      - {variable: DECLINE, label: Decline in score}
  knob_sweep:
    knob: MARKER
    base_profile: {AGE: 72}
    outcomes: [DECLINE]
"""


@pytest.fixture
def v2(tmp_path):
    path = tmp_path / "spec.yml"
    path.write_text(V2, encoding="utf-8")
    return path


def test_the_converted_files_load(v2):
    folder, notes = migrate(v2)
    project = load_project(folder / "settings.yml")
    assert project.design.layer_names == [
        "L0 - Demographics", "L1 - Measurements", "L2 - Outcomes", "L3 - Dropout"]
    assert notes


def test_settings_are_carried_over(v2):
    settings, _, _, _ = convert(yaml.safe_load(V2))
    assert settings["learning"] == {"score": "BIC", "search": "greedy",
                                    "max_parents": 4, "seed": 7}
    assert settings["discretisation"] == {"method": "quantile", "bins": 3,
                                          "categorical_max_levels": 8}
    assert settings["bootstrap"] == {"resamples": 50}
    assert settings["constraints"]["no_parents"] == ["AGE"]


def test_outcomes_become_targets_and_lose_arcs_between_them(v2):
    _, variable_rows, layer_rows, _ = convert(yaml.safe_load(V2))
    targets = {row[0] for row in variable_rows if row[7] == "yes"}
    assert targets == {"DECLINE", "EVENT"}
    inner = {row[0]: row[3] for row in layer_rows}
    assert inner["L2 - Outcomes"] == "no" and inner["L0 - Demographics"] == ""


def test_variants_become_networks_without_the_unused_outcomes(v2):
    settings, _, _, _ = convert(yaml.safe_load(V2))
    decline, joint = settings["networks"]
    assert decline["exclude_variables"] == ["EVENT"]
    assert "exclude_variables" not in joint
    assert joint["exclude_layers"] == ["L1 - Measurements"] and joint["resamples"] == 10


def test_the_selection_layer_rules_are_written_out(v2):
    settings, _, _, notes = convert(yaml.safe_load(V2))
    forbid = settings["constraints"]["forbid"]
    require = settings["constraints"]["require"]
    # Only outcomes may point into the dropout layer ...
    assert {"from_layer": "L0 - Demographics", "to_layer": "L3 - Dropout"} in forbid
    assert {"from_layer": "L1 - Measurements", "to_layer": "L3 - Dropout"} in forbid
    # ... and every outcome is connected to it.
    assert require == [{"from_layer": "L2 - Outcomes", "to_layer": "L3 - Dropout"}]
    assert any("selection layer" in n for n in notes)


def test_analyses_are_converted_and_labels_move_to_the_table(v2):
    settings, variable_rows, _, _ = convert(yaml.safe_load(V2))
    analyses = settings["analyses"]
    assert analyses["importance"] == {"targets": ["DECLINE"]}
    assert analyses["profiles"]["groups"] == {"Older": {"AGE": 80}}
    assert analyses["profiles"]["targets"] == ["DECLINE"]
    assert analyses["profiles"]["resamples"] == 20
    assert analyses["sweep"] == {"variable": "MARKER", "fixed": {"AGE": 72},
                                 "targets": ["DECLINE"]}
    labels = {row[0]: row[1] for row in variable_rows}
    assert labels["DECLINE"] == "Decline in score"


def test_the_converted_networks_obey_the_old_dropout_rules(v2, tmp_path):
    """After conversion only outcomes may point into the dropout variable."""
    import numpy as np
    import pandas as pd

    from layerbn.analysis import Analysis
    rng = np.random.default_rng(0)
    n = 300
    age = rng.normal(70, 8, n)
    df = pd.DataFrame({
        "AGE": age, "SEX": rng.choice(["F", "M"], n),
        "MARKER": age + rng.normal(0, 5, n), "SCORE": rng.normal(0, 1, n),
        "DECLINE": np.where(age + rng.normal(0, 8, n) > 72, "Yes", "No"),
        "EVENT": rng.choice(["Yes", "No"], n),
        "DROPOUT": rng.choice(["A", "B"], n)})
    folder, _ = migrate(v2)
    project = load_project(folder / "settings.yml").with_resamples(2)
    study = Analysis(project, df, verbose=False)
    arcs = study.arcs("joint")
    into_dropout = {p for p, c in arcs if c == "DROPOUT"}
    assert into_dropout <= {"DECLINE", "EVENT"}
    assert {"DECLINE", "EVENT"} <= into_dropout, "outcomes were required to be connected"


def test_a_file_that_is_not_a_version_2_spec_is_refused(tmp_path):
    path = tmp_path / "other.yml"
    path.write_text("name: nothing\n", encoding="utf-8")
    with pytest.raises(MigrationError, match="does not look like a version 2 spec"):
        migrate(path)


def test_the_command_reports_what_it_did(v2, capsys):
    assert main(["migrate", str(v2)]) == 0
    out = capsys.readouterr().out
    assert "settings.yml" in out and "variables.xlsx" in out


def test_loading_a_version_2_spec_as_settings_points_to_migrate(v2, capsys):
    assert main(["check", str(v2)]) == 1
    assert "layerbn migrate" in capsys.readouterr().err
