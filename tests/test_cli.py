"""The command line, which is the first thing a new user touches."""
from __future__ import annotations

import json

import pytest

from layerbn.__main__ import main


def test_init_writes_a_working_project(tmp_path, capsys):
    destination = tmp_path / "my-study"
    assert main(["init", str(destination)]) == 0

    for name in ("spec.yml", "config.yml", "analysis.ipynb", ".gitignore"):
        assert (destination / name).exists(), f"init did not write {name}"

    # And what it wrote must validate.
    assert main(["check", str(destination / "spec.yml")]) == 0


def test_init_refuses_to_overwrite(tmp_path, capsys):
    destination = tmp_path / "my-study"
    main(["init", str(destination)])
    capsys.readouterr()

    assert main(["init", str(destination)]) == 1
    assert "--force" in capsys.readouterr().err


def test_init_force_overwrites(tmp_path):
    destination = tmp_path / "my-study"
    main(["init", str(destination)])
    (destination / "spec.yml").write_text("clobbered", encoding="utf-8")

    assert main(["init", str(destination), "--force"]) == 0
    assert "clobbered" not in (destination / "spec.yml").read_text(encoding="utf-8")


def test_the_written_notebook_is_valid_and_unexecuted(tmp_path):
    """A template shipped with stale outputs would mislead the first reader."""
    destination = tmp_path / "my-study"
    main(["init", str(destination)])
    nb = json.loads((destination / "analysis.ipynb").read_text(encoding="utf-8"))

    assert nb["nbformat"] == 4
    for cell in nb["cells"]:
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is None
            assert cell["outputs"] == []


def test_check_prints_the_layer_order(tmp_path, capsys):
    destination = tmp_path / "my-study"
    main(["init", str(destination)])
    capsys.readouterr()

    main(["check", str(destination / "spec.yml")])
    out = capsys.readouterr().out
    assert "is valid" in out
    # The ordering is the constraint, so `check` has to show it.
    assert out.index("L0 – Demographics") < out.index("L5 – Outcomes")
    assert "[outcome]" in out and "[selection]" in out


def test_check_reports_an_invalid_spec(tmp_path, capsys):
    bad = tmp_path / "spec.yml"
    bad.write_text("name: broken\nlayers: []\n", encoding="utf-8")

    assert main(["check", str(bad)]) == 1
    assert "INVALID" in capsys.readouterr().err


def test_check_suggests_a_correction_for_a_typo(tmp_path, capsys):
    destination = tmp_path / "my-study"
    main(["init", str(destination)])
    spec_path = destination / "spec.yml"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8").replace(
            'exclude_layers: ["L2 – Optional markers"]',
            'exclude_layers: ["L2 - Optional markers"]',  # hyphen, not en dash
            1,
        ),
        encoding="utf-8",
    )

    assert main(["check", str(spec_path)]) == 1
    assert "Did you mean" in capsys.readouterr().err


def test_no_subcommand_exits_with_usage():
    with pytest.raises(SystemExit):
        main([])
