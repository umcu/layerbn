"""Guards against results moving without anyone deciding they should.

Every number the package reports depends on the bins, and the bin edges come
from scikit-learn through pyAgrum. Neither promises to keep them fixed across
versions, and scikit-learn 1.9 is already scheduled to change how quantiles
are computed. These tests pin the edges for a fixed cohort, so that an
upgrade that moves them fails here, loudly, and does not rewrite findings.
"""
from __future__ import annotations

import warnings

import pytest

from layerbn.demo import make_demo_cohort
from layerbn.discretisation import make_type_processor, pretty_labels, state_for_value

# The bin edges for the demo cohort (400 participants, seed 0), recorded per
# pyAgrum release series. They differ between series: pyAgrum 2.3 computes
# quantiles slightly differently from 2.1 (for example 36.25 against 36.275).
# Recorded with numpy 2.1 / pandas 2.2 / scikit-learn 1.8 for pyAgrum 2.1, and
# numpy 2.5 / pandas 3.1 / scikit-learn 1.8 for pyAgrum 2.3.
EXPECTED_BINS_BY_PYAGRUM = {
    "2.1": {
        "AGE": ["(30;53[", "[53;59.5[", "[59.5;66.4[", "[66.4;90)"],
        "EXPOSURE_A": ["(13.1;36.275[", "[36.275;43.4[", "[43.4;52.35[", "[52.35;73.6)"],
        "MEASURE_1": ["(18.4;41.475[", "[41.475;48.45[", "[48.45;54.425[", "[54.425;75.4)"],
        "MEASURE_2": ["(8;18.9[", "[18.9;23.3[", "[23.3;28.2[", "[28.2;43.7)"],
        "MEASURE_3": ["(37.1;81.8[", "[81.8;93.85[", "[93.85;103.7[", "[103.7;137.8)"],
    },
    "2.3": {
        "AGE": ["(30;53[", "[53;59.5[", "[59.5;66.4[", "[66.4;90)"],
        "EXPOSURE_A": ["(13.1;36.25[", "[36.25;43.4[", "[43.4;52.4[", "[52.4;73.6)"],
        "MEASURE_1": ["(18.4;41.45[", "[41.45;48.45[", "[48.45;54.45[", "[54.45;75.4)"],
        "MEASURE_2": ["(8;18.9[", "[18.9;23.3[", "[23.3;28.2[", "[28.2;43.7)"],
        "MEASURE_3": ["(37.1;81.8[", "[81.8;93.85[", "[93.85;103.7[", "[103.7;137.8)"],
    },
}


def pyagrum_series() -> str:
    import pyagrum
    return ".".join(pyagrum.__version__.split(".")[:2])


@pytest.fixture(scope="module")
def expected_bins():
    series = pyagrum_series()
    if series not in EXPECTED_BINS_BY_PYAGRUM:
        pytest.fail(
            f"No bin edges are recorded for pyAgrum {series}. Quantile edges can differ "
            "between pyAgrum versions, and every result depends on them. Print the "
            "edges for the demo cohort, compare them with the recorded series, add "
            "the new series to EXPECTED_BINS_BY_PYAGRUM, and say so in the changelog. "
            "pyproject.toml limits the pyAgrum version for this reason.")
    return EXPECTED_BINS_BY_PYAGRUM[series]


@pytest.fixture(scope="module")
def template():
    df = make_demo_cohort(n=400, seed=0)
    processor = make_type_processor(method="quantile", bins=4, categorical_max_levels=10)
    return processor.discretizedTemplate(df)


def labels(template):
    return {name: list(template.variable(i).labels()) for i, name in template}


@pytest.mark.parametrize("variable", sorted(EXPECTED_BINS_BY_PYAGRUM["2.1"]))
def test_bin_edges_have_not_moved(template, expected_bins, variable):
    assert labels(template)[variable] == expected_bins[variable], (
        f"The bins of {variable!r} changed. Every result that uses these "
        "settings changes with them. If this follows from a dependency upgrade "
        "and you accept it, update EXPECTED_BINS_BY_PYAGRUM and say so in the changelog.")


def test_variables_with_few_values_keep_their_categories(template):
    found = labels(template)
    assert found["SEX"] == ["Female", "Male"]
    assert found["EXPOSURE_B"] == ["No", "Yes"]
    assert found["OUTCOME"] == ["No", "Yes"]


def test_discretisation_is_deterministic():
    df = make_demo_cohort(n=300, seed=3)
    processor = make_type_processor(method="quantile", bins=4, categorical_max_levels=10)
    assert labels(processor.discretizedTemplate(df)) == labels(processor.discretizedTemplate(df))


def test_the_same_seed_gives_the_same_cohort():
    assert make_demo_cohort(50, seed=1).equals(make_demo_cohort(50, seed=1))
    assert not make_demo_cohort(50, seed=1).equals(make_demo_cohort(50, seed=2))


def test_our_own_code_raises_no_deprecation_warnings(project, demo_df):
    """A deprecation ignored today is a breakage after the next upgrade."""
    from layerbn.analysis import Analysis
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        warnings.simplefilter("error", FutureWarning)
        warnings.filterwarnings("ignore", module="sklearn")
        warnings.filterwarnings("ignore", message=".*swigvarlink.*")
        warnings.filterwarnings("ignore", message=".*SwigPy.*")
        warnings.filterwarnings("ignore", message=".*quantile_method.*")
        Analysis(project, demo_df, verbose=False).bins()


# -- reading and writing bin labels ------------------------------------------------------------

def test_interval_labels_become_readable():
    raw = ["(55;67.1[", "[67.1;71.65[", "[71.65;76.5[", "[76.5;92)"]
    # Edges are shown with about three significant digits; the exact edges
    # are in the "Exact edges" column of the bins table.
    assert list(pretty_labels(raw).values()) == ["< 67.1", "67.1 to < 71.7",
                                                 "71.7 to < 76.5", "≥ 76.5"]


def test_category_labels_are_left_alone():
    assert pretty_labels(["No", "Yes"]) == {"No": "No", "Yes": "Yes"}


@pytest.mark.parametrize("value,expected", [
    (60, 0), (67.1, 1), (70, 1), ("71.65", 2), (76.5, 3), (200, 3), (1, 0), ("71,7", 2),
])
def test_a_number_lands_in_the_bin_that_holds_it(value, expected):
    raw = ["(55;67.1[", "[67.1;71.65[", "[71.65;76.5[", "[76.5;92)"]
    assert state_for_value(raw, value) == raw[expected]


@pytest.mark.parametrize("labels,value,expected", [
    (["No", "Yes"], True, "Yes"), (["No", "Yes"], False, "No"),
    (["no", "yes"], True, "yes"), (["Nee", "Ja"], False, "Nee"),
    (["0", "1"], True, "1"), (["A", "B"], True, None),
])
def test_yaml_booleans_match_yes_and_no_categories(labels, value, expected):
    """`OUTCOME: No` in settings.yml arrives as the boolean False."""
    assert state_for_value(labels, value) == expected


def test_a_category_is_matched_by_name_and_unknown_text_is_not():
    assert state_for_value(["No", "Yes"], "Yes") == "Yes"
    assert state_for_value(["No", "Yes"], "Maybe") is None
    assert state_for_value(["No", "Yes"], 3) is None
