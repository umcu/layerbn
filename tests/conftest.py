"""Shared fixtures.

The template spec is the one users actually start from, so most tests load
it rather than a hand-built fixture: a change that breaks the template is a
change that breaks every new project.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "layerbn" / "templates"


@pytest.fixture
def template_spec_path(tmp_path: Path) -> Path:
    """A copy of the shipped spec.yml, in a scratch directory."""
    destination = tmp_path / "spec.yml"
    shutil.copyfile(TEMPLATE_DIR / "spec.yml", destination)
    return destination


@pytest.fixture
def spec(template_spec_path: Path):
    from layerbn.spec import load_spec

    return load_spec(template_spec_path)


@pytest.fixture
def write_spec(tmp_path: Path):
    """Write a spec from a YAML string and return its path."""

    def _write(text: str, name: str = "spec.yml") -> Path:
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path

    return _write


@pytest.fixture(scope="session")
def demo_df():
    from layerbn.demo import make_demo_cohort

    return make_demo_cohort(n=400, seed=0)


MINIMAL_SPEC = """
spec_version: 2
name: minimal
data:
  path: cohort.parquet
layers:
  - name: "L0 - Demographics"
    role: covariate
    variables: [AGE, SEX]
  - name: "L1 - Measurements"
    role: covariate
    variables: [MEASUREMENT A]
  - name: "L2 - Outcomes"
    role: outcome
    variables: [OUTCOME EVENT]
discretisation: {method: quantile, n_bins: 4, threshold: 10}
model: {score: K2, use_tabu: true, max_indegree: 5, seed: 42}
bootstrap: {n: 5}
variants:
  - name: main
    outcomes: [OUTCOME EVENT]
    exclude_layers: []
"""
