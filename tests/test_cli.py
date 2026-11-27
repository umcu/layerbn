"""The command line, as a new user meets it."""
from __future__ import annotations

import re
import shutil

import pytest

from layerbn.__main__ import main


@pytest.fixture
def fresh(tmp_path):
    folder = tmp_path / "study"
    assert main(["init", str(folder)]) == 0
    return folder


# -- init ---------------------------------------------------------------------------

def test_init_writes_a_working_example(fresh):
    for name in ("settings.yml", "variables.xlsx", "data/demo_cohort.csv", ".gitignore"):
        assert (fresh / name).exists(), name
    assert "results/" in (fresh / ".gitignore").read_text()


def test_init_does_not_overwrite_without_force(fresh, capsys):
    (fresh / "settings.yml").write_text("# my edits\n")
    assert main(["init", str(fresh)]) == 1
    assert "already contains" in capsys.readouterr().err
    assert (fresh / "settings.yml").read_text() == "# my edits\n"
    assert main(["init", str(fresh), "--force"]) == 0
    assert "settings_version" in (fresh / "settings.yml").read_text()


def test_a_blank_project_has_empty_tables_and_no_data(tmp_path, capsys):
    folder = tmp_path / "blank"
    assert main(["init", str(folder), "--blank"]) == 0
    assert not (folder / "data").exists()
    assert main(["check", str(folder)]) == 1
    assert "no variables found" in capsys.readouterr().err


def test_init_can_add_a_notebook(tmp_path):
    folder = tmp_path / "nb"
    assert main(["init", str(folder), "--notebook"]) == 0
    assert (folder / "analysis.ipynb").exists()


def test_the_workbook_has_the_dropdowns_and_instructions(fresh):
    from openpyxl import load_workbook
    workbook = load_workbook(fresh / "variables.xlsx")
    assert workbook.sheetnames == ["instructions", "variables", "layers", "timepoints"]
    validations = workbook["variables"].data_validations.dataValidation
    formulas = {v.formula1 for v in validations}
    assert any("layers!" in f for f in formulas)
    assert '"yes,no"' in formulas


# -- check --------------------------------------------------------------------------------

def test_check_accepts_the_folder_or_the_file(fresh, capsys):
    assert main(["check", str(fresh)]) == 0
    assert main(["check", str(fresh / "settings.yml")]) == 0
    out = capsys.readouterr().out
    assert "Settings and design table are valid" in out
    assert "800 participants, all 8 variables found" in out


def test_check_draws_the_layers_on_request(fresh):
    assert main(["check", str(fresh), "--figure"]) == 0
    assert (fresh / "results" / "figures" / "design.png").exists()


def test_check_without_a_data_file_still_checks_the_rest(fresh, capsys):
    (fresh / "data" / "demo_cohort.csv").unlink()
    assert main(["check", str(fresh)]) == 0
    assert "does not exist" in capsys.readouterr().out


def test_a_misspelt_layer_is_explained_without_a_traceback(fresh, capsys):
    from openpyxl import load_workbook
    path = fresh / "variables.xlsx"
    workbook = load_workbook(path)
    workbook["variables"]["C3"] = "Backgroun"           # row 3 is SEX
    workbook.save(path)
    assert main(["check", str(fresh)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("\nError:") and "Traceback" not in err
    assert "'Backgroun'" in err and "Did you mean 'Background'" in err
    assert "row 3" in err or "SEX" in err


def test_a_misspelt_setting_is_explained(fresh, capsys):
    text = (fresh / "settings.yml").read_text().replace("max_parents", "max_parent")
    (fresh / "settings.yml").write_text(text)
    assert main(["check", str(fresh)]) == 1
    assert "learning.max_parent: unknown setting" in capsys.readouterr().err


def test_a_column_that_is_not_in_the_data_is_explained(fresh, capsys):
    import pandas as pd
    path = fresh / "data" / "demo_cohort.csv"
    pd.read_csv(path).rename(columns={"AGE": "Age"}).to_csv(path, index=False)
    assert main(["check", str(fresh)]) == 1
    out = capsys.readouterr().out
    assert "AGE" in out and "is it 'Age'" in out


def test_missing_values_are_explained(fresh, capsys):
    import pandas as pd
    path = fresh / "data" / "demo_cohort.csv"
    frame = pd.read_csv(path)
    frame.loc[:4, "MEASURE_1"] = None
    frame.to_csv(path, index=False)
    assert main(["check", str(fresh)]) == 1
    out = capsys.readouterr().out
    assert "Measure 1: 5 missing" in out and "drop_rows" in out


def test_the_traceback_flag_shows_the_full_error(fresh):
    (fresh / "variables.xlsx").unlink()
    with pytest.raises(Exception, match="no design table"):
        main(["--traceback", "check", str(fresh)])


# -- run ---------------------------------------------------------------------------------------

def shrink(folder, resamples=3):
    text = (folder / "settings.yml").read_text()
    text = re.sub(r"(?m)^(\s*(?:- )?resamples:) \d+.*$", rf"\1 {resamples}", text)
    (folder / "settings.yml").write_text(text)


@pytest.fixture(scope="module")
def finished(tmp_path_factory):
    """One complete run, shared by the tests below."""
    folder = tmp_path_factory.mktemp("run") / "study"
    main(["init", str(folder)])
    shrink(folder)
    assert main(["run", str(folder), "--fast", "--fast-resamples", "4"]) == 0
    return folder / "results"


@pytest.mark.slow
def test_a_run_writes_the_whole_results_folder(finished):
    for name in ("report.html", "tables/tables.xlsx", "inputs/settings.yml",
                 "inputs/variables.xlsx", "inputs/run_info.json",
                 "networks/all_variables.bifxml", "networks/without_exposures.bifxml",
                 "networks/all_variables_explorer.html",
                 "networks/without_exposures_explorer.html",
                 "tables/arcs_all_variables.csv", "tables/importance_all_variables.csv",
                 "tables/profiles.csv", "tables/sweep.csv", "tables/bins.csv",
                 "tables/network_comparison.csv"):
        assert (finished / name).exists(), name
    figures = {p.name for p in (finished / "figures").iterdir()}
    for stem in ("design", "bins", "network_all_variables", "stability_all_variables",
                 "profiles", "sweep", "network_comparison"):
        assert f"{stem}.png" in figures and f"{stem}.pdf" in figures, stem


@pytest.mark.slow
def test_the_report_is_self_contained_and_marks_a_trial_run(finished):
    html = (finished / "report.html").read_text(encoding="utf-8")
    assert html.count("data:image/png;base64") >= 8
    assert "src=\"figures/" not in html and "src=\"http" not in html
    assert "Trial run" in html
    for section in ("Design", "Data and bins", "Network: all_variables", "Profiles",
                    "Sweep", "Comparison of networks", "Methods", "Reproducibility"):
        assert section in html, section


@pytest.mark.slow
def test_the_report_has_a_methods_paragraph_from_the_settings(finished):
    html = (finished / "report.html").read_text(encoding="utf-8")
    assert "Bayesian networks were learned from 800 participants" in html
    assert "K2 score" in html and "random seed 42" in html
    assert "not established causal effects" in html


@pytest.mark.slow
def test_the_saved_network_can_be_reopened(finished):
    import pyagrum as gum
    bn = gum.loadBN(str(finished / "networks" / "all_variables.bifxml"))
    assert len(bn.names()) == 8 and len(bn.arcs()) > 0


@pytest.mark.slow
def test_the_tables_workbook_holds_every_table(finished):
    from openpyxl import load_workbook
    sheets = load_workbook(finished / "tables" / "tables.xlsx").sheetnames
    assert {"bins", "design", "arcs_all_variables", "profiles", "sweep"} <= set(sheets)


@pytest.mark.slow
def test_one_network_can_be_run_alone_with_another_data_file_and_folder(tmp_path):
    folder = tmp_path / "s"
    main(["init", str(folder)])
    shrink(folder)
    moved = tmp_path / "elsewhere.csv"
    shutil.copyfile(folder / "data" / "demo_cohort.csv", moved)
    (folder / "data" / "demo_cohort.csv").unlink()
    out = tmp_path / "out"
    assert main(["run", str(folder), "--network", "all_variables", "--data", str(moved),
                 "--output", str(out), "--no-pdf", "--fast", "--fast-resamples", "3"]) == 0
    assert (out / "report.html").exists()
    assert not (out / "networks" / "without_exposures.bifxml").exists()
    assert not list((out / "figures").glob("*.pdf"))
    assert not (out / "tables" / "network_comparison.csv").exists()


def test_run_names_an_unknown_network(fresh, capsys):
    assert main(["run", str(fresh), "--network", "nope", "--fast"]) == 1
    assert "no network named 'nope'" in capsys.readouterr().err


def test_a_run_survives_a_profile_that_cannot_be_used(tmp_path):
    folder = tmp_path / "s"
    main(["init", str(folder)])
    shrink(folder, 2)
    text = (folder / "settings.yml").read_text().replace("SEX: Female", "SEX: Unknown")
    (folder / "settings.yml").write_text(text)
    from layerbn.runner import run_project
    result = run_project(folder / "settings.yml", fast=True, fast_resamples=2,
                         networks=["all_variables"], formats=("png",), verbose=False)
    assert result.report_path.exists()
