"""Shared fixtures.

Most tests use the worked example that `layerbn init` creates, because that is
what a new user starts from: a change that breaks the example breaks every new
project. Bootstrap counts are cut to a handful so the suite stays fast.
"""
from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest

from layerbn.__main__ import main

warnings.filterwarnings("ignore")


def _small(settings_text: str, resamples: int = 5) -> str:
    """The example settings with every bootstrap count replaced."""
    return re.sub(r"(?m)^(\s*(?:- )?resamples:) \d+.*$", rf"\1 {resamples}", settings_text)


@pytest.fixture(scope="session")
def demo_dir(tmp_path_factory) -> Path:
    """A project folder created by `layerbn init`, with small bootstrap counts."""
    folder = tmp_path_factory.mktemp("demo") / "study"
    assert main(["init", str(folder)]) == 0
    settings = folder / "settings.yml"
    settings.write_text(_small(settings.read_text(encoding="utf-8")), encoding="utf-8")
    return folder


@pytest.fixture(scope="session")
def settings_path(demo_dir) -> Path:
    return demo_dir / "settings.yml"


@pytest.fixture(scope="session")
def project(settings_path):
    from layerbn.project import load_project
    return load_project(settings_path)


@pytest.fixture(scope="session")
def demo_df():
    from layerbn.demo import make_demo_cohort
    return make_demo_cohort(n=400, seed=0)


@pytest.fixture(scope="session")
def study(project, demo_df):
    from layerbn.analysis import Analysis
    return Analysis(project, demo_df, verbose=False)


@pytest.fixture
def make_project(demo_dir, tmp_path):
    """Build a project from the example workbook and a settings text of your own."""
    import shutil

    from layerbn.project import load_project

    def build(settings_text: str):
        shutil.copyfile(demo_dir / "variables.xlsx", tmp_path / "variables.xlsx")
        (tmp_path / "settings.yml").write_text(
            "settings_version: 3\n" + settings_text, encoding="utf-8")
        return load_project(tmp_path / "settings.yml")

    return build


@pytest.fixture
def write_tables(tmp_path):
    """Write design tables as CSV and return the path of `variables.csv`."""

    def write(variables: str, layers: str | None = None,
              timepoints: str | None = None) -> Path:
        (tmp_path / "variables.csv").write_text(variables.strip() + "\n", encoding="utf-8")
        if layers:
            (tmp_path / "layers.csv").write_text(layers.strip() + "\n", encoding="utf-8")
        if timepoints:
            (tmp_path / "timepoints.csv").write_text(timepoints.strip() + "\n",
                                                     encoding="utf-8")
        return tmp_path / "variables.csv"

    return write
