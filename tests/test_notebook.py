"""The optional notebook, executed as a user would run it."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from layerbn.__main__ import main

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")
# Running a notebook also needs a registered kernel, which nbclient does not
# install. Without this the suite would error on a [dev]-only install.
pytest.importorskip("ipykernel", reason="no Jupyter kernel; install .[notebook]")

TEMPLATE = Path(__file__).resolve().parents[1] / "layerbn" / "templates" / "analysis.ipynb"


@pytest.fixture(scope="module")
def executed(tmp_path_factory):
    project = tmp_path_factory.mktemp("nb") / "study"
    main(["init", str(project), "--notebook"])
    text = (project / "settings.yml").read_text()
    (project / "settings.yml").write_text(
        re.sub(r"(?m)^(\s*(?:- )?resamples:) \d+.*$", r"\1 3", text))

    notebook = nbformat.read(project / "analysis.ipynb", as_version=4)
    client = nbclient.NotebookClient(
        notebook, timeout=900, kernel_name="python3",
        resources={"metadata": {"path": str(project)}})
    client.execute()
    return notebook


@pytest.mark.slow
def test_every_cell_runs(executed):
    for i, cell in enumerate(executed.cells):
        for output in cell.get("outputs", []):
            assert output.get("output_type") != "error", (
                f"cell {i} raised {output.get('ename')}: {output.get('evalue')}")


@pytest.mark.slow
def test_the_notebook_shows_figures(executed):
    images = sum(
        1 for cell in executed.cells for out in cell.get("outputs", [])
        if "image/png" in out.get("data", {}))
    assert images >= 6


def test_the_notebook_ships_unexecuted():
    """Committed outputs would show results nobody reproduced."""
    notebook = nbformat.read(TEMPLATE, as_version=4)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            assert cell.execution_count is None and cell.outputs == []


def test_the_notebook_has_no_hard_coded_variable_names():
    """Everything comes from the project files, so it works for any study."""
    notebook = nbformat.read(TEMPLATE, as_version=4)
    code = "\n".join(c.source for c in notebook.cells if c.cell_type == "code")
    for name in ("AGE", "EXPOSURE_A", "MEASURE_1", "OUTCOME"):
        assert name not in code
