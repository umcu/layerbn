"""The template notebook, executed exactly as a new user would run it.

The README's central promise is "run it once, unchanged, and it works".
Nothing else in the suite tests that promise end to end, and it is the one
most easily broken by a change somewhere else.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from layerbn.__main__ import main

pytestmark = pytest.mark.slow

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")


@pytest.fixture(scope="module")
def executed_notebook(tmp_path_factory):
    project = tmp_path_factory.mktemp("study")
    main(["init", str(project), "--force"])

    notebook = nbformat.read(project / "analysis.ipynb", as_version=4)
    client = nbclient.NotebookClient(
        notebook,
        timeout=1800,
        kernel_name="python3",
        resources={"metadata": {"path": str(project)}},
    )
    client.execute()
    return notebook, project


def test_every_cell_runs(executed_notebook):
    notebook, _ = executed_notebook
    for i, cell in enumerate(notebook.cells):
        for output in cell.get("outputs", []):
            assert output.get("output_type") != "error", (
                f"cell {i} raised {output.get('ename')}: {output.get('evalue')}"
            )


def test_it_writes_the_outputs_the_readme_promises(executed_notebook):
    _, project = executed_notebook
    outputs = project / "outputs"
    expected = [
        "network_joint.pdf",
        "network_joint.bifxml",
        "edge_stability_joint.csv",
        "information_joint.csv",
        "scenario_risks_joint.csv",
        "knob_sweep_joint.csv",
    ]
    written = {p.name for p in outputs.iterdir()}
    assert set(expected) <= written, f"missing: {set(expected) - written}"


def test_the_saved_network_can_be_reopened(executed_notebook):
    """The .bifxml is advertised as reusable without redoing the analysis."""
    import pyagrum as gum

    _, project = executed_notebook
    bn = gum.loadBN(str(project / "outputs" / "network_joint.bifxml"))
    assert len(bn.names()) > 0
    assert len(bn.arcs()) > 0


def test_it_does_not_flood_the_output_with_solver_notifications(executed_notebook):
    """aGrUM prints a bias notification per fit if the prior is misconfigured."""
    notebook, _ = executed_notebook
    text = "\n".join(
        output.get("text", "")
        for cell in notebook.cells
        for output in cell.get("outputs", [])
        if output.get("output_type") == "stream"
    )
    assert "already contains a different 'implicit' prior" not in text


def test_the_template_notebook_ships_unexecuted():
    """Committed outputs would show results nobody reproduced."""
    source = Path(__file__).resolve().parents[1] / "layerbn" / "templates" / "analysis.ipynb"
    notebook = nbformat.read(source, as_version=4)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            assert cell.execution_count is None
            assert cell.outputs == []
