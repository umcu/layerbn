"""Guards against results moving without anyone deciding they should.

Every number this package reports is conditional on the discretisation, so
a change in bin edges is a change in every result. The edges come from
scikit-learn, via pyAgrum, neither of which promises to keep them fixed
across versions — scikit-learn 1.9 is already scheduled to change how
quantiles are computed.

These tests pin the edges for a fixed cohort. If a dependency upgrade moves
them, this fails loudly instead of silently rewriting your findings.
"""
from __future__ import annotations

import warnings

import pytest

from layerbn.analysis import Analysis
from layerbn.demo import make_demo_cohort
from layerbn.discretisation import make_type_processor

# Recorded on numpy 2.1, pandas 2.2, scikit-learn 1.8, pyagrum 2.1.
EXPECTED_BINS = {
    "AGE": ["(45.0;64.4[", "(64.4;69.6[", "(69.6;75.1[", "(75.1;94.5["],
    "EDUCATION YEARS": ["(5.0;11.0[", "(11.0;13.0[", "(13.0;15.0[", "(15.0;21.0["],
    "RISK SCORE": ["(10.9;43.9[", "(43.9;54.2[", "(54.2;63.5[", "(63.5;91.9["],
    "MEASUREMENT B": ["(1.8;3.0[", "(3.0;3.3[", "(3.3;3.6[", "(3.6;4.3["],
    "BASELINE TEST SCORE": ["(16.0;26.0[", "(26.0;28.0[", "(28.0;29.0[", "(29.0;30.0["],
}


@pytest.fixture(scope="module")
def bins(spec_from_template):
    study = Analysis(spec_from_template, make_demo_cohort(n=400, seed=0), verbose=False)
    table = study.bins("joint")
    return {row.variable: list(row.labels) for row in table.itertuples()}


@pytest.fixture(scope="module")
def spec_from_template():
    import shutil
    from pathlib import Path
    from tempfile import mkdtemp

    from layerbn.spec import load_spec

    templates = Path(__file__).resolve().parents[1] / "layerbn" / "templates"
    workdir = Path(mkdtemp())
    shutil.copyfile(templates / "spec.yml", workdir / "spec.yml")
    return load_spec(workdir / "spec.yml")


@pytest.mark.parametrize("variable", sorted(EXPECTED_BINS))
def test_bin_edges_have_not_moved(bins, variable):
    assert bins[variable] == EXPECTED_BINS[variable], (
        f"The discretisation of {variable!r} changed. Every result in every "
        "analysis using these settings changes with it. If this is an "
        "intended consequence of a dependency upgrade, update EXPECTED_BINS "
        "and say so in the changelog."
    )


def test_variables_below_the_threshold_are_left_alone(bins):
    """`threshold: 10` means few-valued columns keep their own categories."""
    assert bins["SEX"] == ["Female", "Male"]
    assert bins["COMORBIDITY COUNT"] == ["0", "1", "2", "3"]
    assert bins["OUTCOME EVENT"] == ["No", "Yes"]


def test_discretisation_is_deterministic():
    df = make_demo_cohort(n=300, seed=3)
    processor = make_type_processor(method="quantile", n_bins=4, threshold=10)
    first = processor.discretizedTemplate(df)
    second = processor.discretizedTemplate(df)
    labels = lambda t: {  # noqa: E731
        t.variable(i).name(): list(t.variable(i).labels()) for i in range(t.size())
    }
    assert labels(first) == labels(second)


def test_no_deprecation_warnings_from_our_own_code():
    """A deprecation we ignore today is a breakage on the next upgrade."""
    df = make_demo_cohort(n=100, seed=0)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        warnings.simplefilter("error", FutureWarning)
        from layerbn.preprocess import coalesce, impute_dataframe, translate_labels

        frame = df.copy()
        impute_dataframe(frame)
        coalesce(frame, ["AGE"], "AGE COPY")
        translate_labels(frame, {"SEX": {"Female": "F"}})
