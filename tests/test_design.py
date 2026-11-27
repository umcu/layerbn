"""The design tables: variables, layers and time points."""
from __future__ import annotations

import pytest

from layerbn.design import DesignError, load_design

VARIABLES = """
variable,label,layer,type,bins,cutpoints,times,target
AGE,Age,Background,,,,,
SEX,Sex,Background,categorical,,,,
SCORE,Score,Scores,,,,,
TEST,Test result,Scores,,,,T0;T2,
STATUS,Status,Status,,,,,yes
OUT,Outcome,Outcome,,,,,yes
"""
LAYERS = """
layer,label,repeated,arcs_within,colour
Background,,no,,
Scores,,yes,,
Status,,yes,,
Outcome,,no,no,
"""
TIMES = """
time,label
T0,First visit
T1,Second visit
T2,Third visit
"""


def test_the_example_workbook_has_no_repeated_layers(project):
    assert project.design.layer_names == [
        "Background", "Exposures", "Baseline measures", "Outcome"]
    assert project.design.timepoints == ()
    assert project.design.layer_map["Baseline measures"] == [
        "MEASURE_1", "MEASURE_2", "MEASURE_3"]


def test_repeated_layers_are_expanded_in_time_order(write_tables):
    design = load_design(write_tables(VARIABLES, LAYERS, TIMES))
    assert design.layer_names == [
        "Background",
        "Scores (First visit)", "Status (First visit)",
        "Scores (Second visit)", "Status (Second visit)",
        "Scores (Third visit)", "Status (Third visit)",
        "Outcome",
    ]


def test_a_variable_can_be_limited_to_some_time_points(write_tables):
    design = load_design(write_tables(VARIABLES, LAYERS, TIMES))
    assert "TEST_T0" in design.columns and "TEST_T2" in design.columns
    assert "TEST_T1" not in design.columns
    assert design.layer_map["Scores (Second visit)"] == ["SCORE_T1"]


def test_the_column_pattern_can_be_changed(write_tables):
    design = load_design(write_tables(VARIABLES, LAYERS, TIMES),
                         column_pattern="{time}__{variable}")
    assert "T0__SCORE" in design.columns


def test_labels_include_the_time_point_and_stay_unique(write_tables):
    design = load_design(write_tables(VARIABLES, LAYERS, TIMES))
    assert design.label("SCORE_T1") == "Score, Second visit"
    assert design.variable("SCORE_T1").short_label == "Score"
    labels = [v.label for v in design.variables]
    assert len(labels) == len(set(labels))


def test_without_a_layers_sheet_layers_follow_first_appearance(write_tables):
    path = write_tables("""
variable,layer
A,Second
B,First
C,Second
""")
    design = load_design(path)
    assert design.layer_names == ["Second", "First"]
    assert design.layer_map == {"Second": ["A", "C"], "First": ["B"]}


def test_a_repeated_layer_has_the_same_colour_at_every_time_point(write_tables):
    design = load_design(write_tables(VARIABLES, LAYERS, TIMES))
    colours = {layer.colour for layer in design.layers if layer.key == "Scores"}
    assert len(colours) == 1
    other = {layer.colour for layer in design.layers if layer.key == "Status"}
    assert colours != other


def test_a_colour_can_be_set_and_is_checked(write_tables):
    ok = write_tables("variable,layer\nA,X\nB,X", "layer,colour\nX,steelblue")
    assert load_design(ok).layers[0].colour == "#4682b4"
    bad = write_tables("variable,layer\nA,X\nB,X", "layer,colour\nX,notacolour")
    with pytest.raises(DesignError, match="not a colour"):
        load_design(bad)


def test_variables_resolve_by_column_or_label(write_tables):
    design = load_design(write_tables(VARIABLES, LAYERS, TIMES))
    assert design.resolve_variable("SCORE_T1") == "SCORE_T1"
    assert design.resolve_variable("Score, Second visit") == "SCORE_T1"
    assert design.resolve_variable("score, Second visit") == "SCORE_T1"
    with pytest.raises(DesignError, match="Did you mean 'SCORE_T1'"):
        design.resolve_variable("SCORE_T11")


def test_a_layer_name_stands_for_all_time_points(write_tables):
    design = load_design(write_tables(VARIABLES, LAYERS, TIMES))
    assert design.resolve_layers("Scores") == [
        "Scores (First visit)", "Scores (Second visit)", "Scores (Third visit)"]
    assert design.resolve_layers("Scores (Second visit)") == ["Scores (Second visit)"]


def test_the_cutpoints_accept_a_decimal_comma(write_tables):
    path = write_tables('variable,layer,cutpoints\nA,X,"24,5; 27"\nB,X,')
    assert load_design(path).variable("A").cutpoints == (24.5, 27.0)


def test_columns_named_note_are_ignored(write_tables):
    path = write_tables("variable,layer,note\nA,X,measured by the nurse\nB,X,")
    assert load_design(path).columns == ["A", "B"]


# -- mistakes a user can make -------------------------------------------------

def test_an_unknown_column_header_is_reported_with_a_suggestion(write_tables):
    path = write_tables("variable,layer,lable\nA,X,a\nB,X,b")
    with pytest.raises(DesignError, match="unknown column 'lable'.*Did you mean 'label'"):
        load_design(path)


def test_a_layer_missing_from_the_layers_sheet_is_reported(write_tables):
    path = write_tables("variable,layer\nA,Backgroun\nB,Other",
                        "layer\nBackground\nOther")
    with pytest.raises(DesignError, match="'Backgroun'.*Did you mean 'Background'"):
        load_design(path)


def test_a_variable_listed_twice_is_reported_with_both_rows(write_tables):
    path = write_tables("variable,layer\nA,X\nB,X\nA,Y")
    with pytest.raises(DesignError, match="row 4.*first on row 2"):
        load_design(path)


def test_repeated_layers_need_time_points(write_tables):
    with pytest.raises(DesignError, match="no 'timepoints' sheet"):
        load_design(write_tables(VARIABLES, LAYERS))


def test_repeated_layers_must_be_adjacent(write_tables):
    layers = "layer,repeated\nBackground,no\nScores,yes\nStatus,no\nOutcome,yes"
    path = write_tables(
        "variable,layer\nAGE,Background\nSCORE,Scores\nSTATUS,Status\nOUT,Outcome",
        layers, TIMES)
    with pytest.raises(DesignError, match="must follow each other"):
        load_design(path)


def test_times_must_be_defined(write_tables):
    path = write_tables("variable,layer,times\nA,X,T9\nB,X,", "layer,repeated\nX,yes",
                        "time\nT0")
    with pytest.raises(DesignError, match="'T9' is not on the 'timepoints' sheet"):
        load_design(path)


def test_bins_and_cutpoints_exclude_each_other(write_tables):
    path = write_tables("variable,layer,bins,cutpoints\nA,X,3,24\nB,X,,")
    with pytest.raises(DesignError, match="either 'bins' or 'cutpoints'"):
        load_design(path)


def test_a_categorical_variable_cannot_be_binned(write_tables):
    path = write_tables("variable,layer,type,bins\nA,X,categorical,3\nB,X,,")
    with pytest.raises(DesignError, match="not binned"):
        load_design(path)


def test_the_type_must_be_known(write_tables):
    path = write_tables("variable,layer,type\nA,X,numeric\nB,X,")
    with pytest.raises(DesignError, match="'numeric' is not allowed"):
        load_design(path)


def test_yes_and_no_fields_are_checked(write_tables):
    path = write_tables("variable,layer,target\nA,X,maybe\nB,X,")
    with pytest.raises(DesignError, match="expected yes or no"):
        load_design(path)


def test_a_layer_without_variables_is_reported(write_tables):
    path = write_tables("variable,layer\nA,X", "layer\nX\nY")
    with pytest.raises(DesignError, match="layer 'Y' has no variables"):
        load_design(path)


def test_a_missing_file_is_reported(tmp_path):
    with pytest.raises(DesignError, match="not found"):
        load_design(tmp_path / "nothing.xlsx")


def test_a_blank_workbook_says_it_is_empty(tmp_path):
    from layerbn.workbook import write_design_workbook
    path = write_design_workbook(tmp_path / "blank.xlsx", demo=False)
    with pytest.raises(DesignError, match="no variables found"):
        load_design(path)


def test_times_on_a_layer_that_is_not_repeated_is_reported(write_tables):
    path = write_tables("variable,layer,times\nA,X,T0\nB,X,", "layer,repeated\nX,no",
                        "time\nT0")
    with pytest.raises(DesignError, match="is not repeated"):
        load_design(path)
