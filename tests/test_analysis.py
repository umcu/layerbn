"""The Analysis object: data checks, tables, profiles and sweeps."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from layerbn.analysis import Analysis, DataError

# -- checking the data ----------------------------------------------------------------

def test_a_missing_column_is_listed_with_a_suggestion(project, demo_df):
    broken = demo_df.rename(columns={"MEASURE_2": "MEASURE_02"})
    with pytest.raises(DataError, match=r"(?s)1 variable\(s\).*MEASURE_2.*is it 'MEASURE_02'"):
        Analysis(project, broken, verbose=False)


def test_the_message_for_a_missing_column_mentions_the_pattern(
        make_project, write_tables, demo_df):
    write_tables("variable,layer\nAGE,Background\nSCORE,Visits\nOUTCOME,Outcome",
                 "layer,repeated\nBackground,no\nVisits,yes\nOutcome,no",
                 "time,label\nT0,First visit\nT1,Second visit")
    p = make_project("data: {variables_file: variables.csv}")
    frame = demo_df.assign(SCORE_T0=demo_df["MEASURE_1"])       # SCORE_T1 is missing
    with pytest.raises(DataError, match=r"\{variable\}_\{time\}"):
        Analysis(p, frame, verbose=False)


def test_missing_values_stop_the_analysis_and_say_where(project, demo_df):
    holes = demo_df.copy()
    holes.loc[:9, "AGE"] = np.nan
    with pytest.raises(DataError, match=r"Age \(years\): 10 missing"):
        Analysis(project, holes, verbose=False)


def test_complete_cases_can_be_chosen_and_are_reported(make_project, demo_df):
    p = make_project("data: {missing: drop_rows}")
    holes = demo_df.copy()
    holes.loc[:9, "AGE"] = np.nan
    study = Analysis(p, holes, verbose=False)
    assert study.n == len(demo_df) - 10 and study.n_input == len(demo_df)
    assert any("10 of 400 participants" in note for note in study.notes)


def test_a_constant_variable_is_refused(project, demo_df):
    constant = demo_df.assign(MEASURE_1=12)
    with pytest.raises(DataError, match="only one value.*Measure 1"):
        Analysis(project, constant, verbose=False)


def test_extra_columns_are_noted_and_not_used(project, demo_df):
    study = Analysis(project, demo_df.assign(PATIENT_ID=range(len(demo_df))), verbose=False)
    assert "PATIENT_ID" not in study.df.columns
    assert any("PATIENT_ID" in note for note in study.notes)


def test_a_text_column_cannot_be_forced_to_continuous(make_project, write_tables, demo_df):
    write_tables("variable,layer,type\nSEX,X,continuous\nAGE,X,\nOUTCOME,Y,",)
    p = make_project("data: {variables_file: variables.csv}")
    with pytest.raises(DataError, match="not numeric"):
        Analysis(p, demo_df, verbose=False)


def test_a_csv_saved_by_excel_with_semicolons_is_read(tmp_path):
    from layerbn.analysis import read_table
    path = tmp_path / "data.csv"
    path.write_text("AGE;SCORE;GROUP\n63,5;12,25;A\n70,1;9,5;B\n", encoding="utf-8")
    frame = read_table(path)
    assert list(frame.columns) == ["AGE", "SCORE", "GROUP"]
    assert frame["AGE"].tolist() == [63.5, 70.1]


def test_an_ordinary_csv_is_read(tmp_path):
    from layerbn.analysis import read_table
    path = tmp_path / "data.csv"
    path.write_text("AGE,GROUP\n63.5,A\n70.1,B\n", encoding="utf-8")
    assert read_table(path)["AGE"].tolist() == [63.5, 70.1]


# -- tables ------------------------------------------------------------------------------

def test_the_bins_are_described_in_readable_terms(study):
    bins = study.bins().set_index("Variable")
    assert bins.loc["Age (years)", "Treated as"] == "continuous, binned"
    assert bins.loc["Age (years)", "States"] == 4
    assert bins.loc["Age (years)", "Bins or categories"].startswith("< ")
    assert "≥" in bins.loc["Age (years)", "Bins or categories"]
    assert bins.loc["Sex", "Treated as"] == "categorical"
    assert bins.loc["Sex", "Bins or categories"] == "Female | Male"
    # The exact edges are given, since the readable names are rounded.
    assert bins.loc["Age (years)", "Exact edges"].count(";") == 4
    assert bins.loc["Sex", "Exact edges"] == ""


def test_stable_edges_is_a_complete_table(study):
    table = study.stable_edges("all_variables")
    assert list(table.columns) == ["Parent", "Child", "Parent layer", "Child layer",
                                   "Frequency", "In network", "Mutual information (bits)"]
    assert table["Frequency"].between(0, 1).all()
    assert table["Frequency"].is_monotonic_decreasing
    assert table["Mutual information (bits)"].dropna().ge(0).all()
    # Every arc of the learned network is in the table, flagged.
    assert table["In network"].sum() <= len(study.arcs("all_variables"))


def test_stable_edges_can_be_filtered(study):
    everything = study.stable_edges("all_variables")
    assert len(study.stable_edges("all_variables", min_frequency=0.8)) <= len(everything)


def test_networks_can_be_compared(study):
    table = study.compare_networks()
    assert list(table.columns)[:2] == ["Parent", "Child"]
    assert set(table.columns[2:]) == {"all_variables", "without_exposures"}
    # An arc that needs a variable that is left out cannot occur in that network.
    row = table[(table["Parent"] == "Age (years)") & (table["Child"] == "Exposure A (score)")]
    if len(row):
        assert row["without_exposures"].isna().all()


def test_importance_reports_relation_and_distance(study):
    table = study.importance("all_variables", targets=["OUTCOME"])
    column = "Mutual information (bits)"
    assert set(table["Relation"]) <= {"parent", "child", "co-parent", "other"}
    assert table[column].dropna().ge(0).all()
    assert table[column].is_monotonic_decreasing
    parents = {study.label(p) for p, c in study.arcs("all_variables") if c == "OUTCOME"}
    assert set(table.loc[table["Relation"] == "parent", "Variable"]) == parents
    assert (table.loc[table["Relation"] == "parent", "Arcs"] == 1).all()
    assert "CMI" not in table.columns


def test_importance_skips_a_target_that_is_not_in_the_network(study):
    table = study.importance("without_exposures", targets=["EXPOSURE_A"])
    assert table.empty
    assert any("not in network" in note for note in study.notes)


def test_importance_uses_the_marked_targets_by_default(project, demo_df):
    fresh = Analysis(project, demo_df, verbose=False)
    table = fresh.importance("all_variables")
    assert "Outcome at follow-up" in set(table["Target"])


# -- profiles -----------------------------------------------------------------------------

def test_a_value_is_placed_in_its_bin_and_the_note_says_so(project, demo_df):
    fresh = Analysis(project, demo_df, verbose=False)
    applied = fresh.resolve_profile("all_variables", {"AGE": 65, "SEX": "Female"})
    assert set(applied) == {"AGE", "SEX"}
    assert any("Age (years): 65 ->" in note for note in fresh.notes)


def test_values_can_be_written_as_in_the_bins_table(project, demo_df):
    fresh = Analysis(project, demo_df, verbose=False)
    label = fresh.bins().set_index("Variable").loc["Age (years)", "Bins or categories"]
    last = label.split(" | ")[-1]
    applied = fresh.resolve_profile("all_variables", {"AGE": last})
    assert applied["AGE"] == 3


def test_an_unquoted_yes_or_no_in_a_profile_is_understood(project, demo_df):
    import yaml
    fixed = yaml.safe_load("OUTCOME: No")          # PyYAML gives False
    assert fixed["OUTCOME"] is False
    fresh = Analysis(project, demo_df, verbose=False)
    applied = fresh.resolve_profile("all_variables", fixed)
    assert applied == {"OUTCOME": 0}


def test_values_that_do_not_fit_are_reported_and_left_out(project, demo_df):
    fresh = Analysis(project, demo_df, verbose=False)
    applied = fresh.resolve_profile(
        "all_variables", {"SEX": "F", "AGE": 70, "EXPOSURE_A": 50}, label="group")
    assert set(applied) == {"AGE", "EXPOSURE_A"}
    assert any("NOT USED" in n and "Sex='F'" in n and "Female" in n for n in fresh.notes)


def test_a_variable_outside_the_network_is_reported(project, demo_df):
    fresh = Analysis(project, demo_df, verbose=False)
    fresh.resolve_profile("without_exposures", {"EXPOSURE_A": 50, "AGE": 70})
    assert any("not in network" in n for n in fresh.notes)


def test_profile_probabilities_are_proper_and_ordered(study):
    table = study.profiles()
    needed = {"Profile", "Target", "State", "Probability", "CI 2.5%", "CI 97.5%"}
    assert needed <= set(table.columns)
    assert table["Probability"].between(0, 1).all()
    assert (table["CI 2.5%"] <= table["Probability"] + 1e-9).all()
    assert (table["Probability"] <= table["CI 97.5%"] + 1e-9).all()
    # The states of one target sum to one in each profile.
    totals = table.groupby(["Profile", "Target"])["Probability"].sum()
    assert np.allclose(totals, 1.0, atol=1e-6)


def test_a_profile_with_no_usable_value_is_an_error(make_project, demo_df):
    p = make_project("""
bootstrap: {resamples: 2}
analyses:
  profiles:
    groups: {"nothing": {SEX: "Unknown"}}
""")
    with pytest.raises(ValueError, match="No value of the profile"):
        Analysis(p, demo_df, verbose=False).profiles()


def test_profiles_without_a_definition_are_an_error(make_project, demo_df):
    p = make_project("bootstrap: {resamples: 2}")
    with pytest.raises(ValueError, match="No profiles are defined"):
        Analysis(p, demo_df, verbose=False).profiles()


# -- sweep -----------------------------------------------------------------------------------

def test_a_sweep_covers_every_state_of_the_variable(study):
    table, meta = study.sweep()
    assert meta["variable"] == "Exposure A (score)"
    assert len(meta["variable_states"]) == 4
    assert set(table["variable_state"]) == set(meta["variable_states"])
    totals = table.groupby("variable_state")["probability"].sum()
    assert np.allclose(totals, 1.0, atol=1e-6)


def test_fixing_something_downstream_of_the_moved_variable_is_noted(make_project, demo_df):
    p = make_project("""
bootstrap: {resamples: 3}
analyses:
  sweep:
    variable: EXPOSURE_A
    fixed: {MEASURE_3: 100}
    targets: [OUTCOME]
""")
    fresh = Analysis(p, demo_df, verbose=False)
    fresh.sweep()
    assert any("downstream" in n for n in fresh.notes)


# -- discretisation overrides ------------------------------------------------------------

def test_cutpoints_bins_and_types_from_the_design_table(make_project, write_tables, demo_df):
    frame = demo_df.assign(GROUP=np.arange(len(demo_df)) % 12)    # 12 numeric codes
    write_tables(
        "variable,layer,type,bins,cutpoints,target\n"
        "AGE,X,,,\"50; 70\",\n"
        "GROUP,X,categorical,,,\n"
        "EXPOSURE_A,X,,2,,\n"
        "OUTCOME,Y,,,,yes")
    p = make_project("data: {variables_file: variables.csv}")
    bins = Analysis(p, frame, verbose=False).bins().set_index("Variable")
    assert bins.loc["AGE", "States"] == 3
    assert bins.loc["AGE", "Bins or categories"] == "< 50 | 50 to < 70 | ≥ 70"
    assert bins.loc["GROUP", "Treated as"] == "categorical"
    assert bins.loc["GROUP", "States"] == 12
    assert bins.loc["EXPOSURE_A", "States"] == 2


def test_a_continuous_variable_with_few_values_can_be_forced_to_bins(
        make_project, write_tables, demo_df):
    frame = demo_df.assign(SCORE=np.arange(len(demo_df)) % 6)
    write_tables("variable,layer,type\nSCORE,X,continuous\nAGE,X,\nOUTCOME,Y,")
    p = make_project("data: {variables_file: variables.csv}")
    bins = Analysis(p, frame, verbose=False).bins().set_index("Variable")
    assert bins.loc["SCORE", "Treated as"] == "continuous, binned"


# -- reproducibility ---------------------------------------------------------------------------

def test_the_same_settings_give_the_same_network(project, demo_df):
    first = Analysis(project, demo_df, verbose=False).arcs("all_variables")
    second = Analysis(project, demo_df, verbose=False).arcs("all_variables")
    assert sorted(first) == sorted(second)


def test_frequencies_are_reproducible_with_the_seed(project, demo_df):
    one = Analysis(project, demo_df, verbose=False).edge_frequencies("all_variables")
    two = Analysis(project, demo_df, verbose=False).edge_frequencies("all_variables")
    assert one == two


def test_summary_describes_data_and_project(study):
    text = study.summary()
    assert "400 participants" in text and "Baseline measures" in text


def test_the_columns_are_the_ones_declared(study):
    assert isinstance(study.df, pd.DataFrame)
    assert list(study.df.columns) == study.design.columns
