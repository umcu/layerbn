"""A simulated cohort, so that the whole workflow can be tried before real data is ready.

The cohort has the most common design: characteristics measured once at
baseline, and an outcome observed at follow-up.

    Background          age, sex
    Exposures           exposure A (a score), exposure B (yes/no)
    Baseline measures   measure 1, measure 2, measure 3
    Outcome             outcome at follow-up (yes/no)

The names are deliberately general. Replace them with your own variables:
nothing in layerbn depends on what the variables are, only on the layer
each one is in.

The arcs that generated the data are listed in `TRUE_EDGES`, so a learned
network can be compared with the truth, which is impossible with real data.
The effect sizes are invented. The data describe no real person and support
no scientific claim.

    from layerbn.demo import make_demo_cohort
    df = make_demo_cohort(n=800, seed=0)
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _logistic(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def make_demo_cohort(n: int = 800, seed: int = 0) -> pd.DataFrame:
    """Simulate `n` participants. The same seed gives the same cohort.

    Effects are larger than in a real cohort. Structure learning on a few
    bins needs a clear signal to recover an arc, and a demo whose network came
    back almost empty would give a wrong impression of the method.
    """
    rng = np.random.default_rng(seed)

    # -- background ----------------------------------------------------------------
    age = rng.normal(60, 10, n).clip(30, 90)
    male = rng.binomial(1, 0.5, n)

    # -- exposures -------------------------------------------------------------------
    exposure_a = (40 + 0.7 * (age - 60) + 9.0 * male + rng.normal(0, 9, n)).clip(0, 100)
    exposure_b = rng.binomial(1, _logistic(-0.4 + 0.08 * (age - 60)))

    # -- baseline measures -------------------------------------------------------
    measure_1 = 50 - 0.45 * (age - 60) - 0.40 * (exposure_a - 40) + rng.normal(0, 5, n)
    measure_2 = 20 + 0.30 * (exposure_a - 40) + 7.0 * exposure_b + rng.normal(0, 3.5, n)
    measure_3 = (100 + 0.9 * (measure_1 - 50) - 1.3 * (measure_2 - 20)
                 + rng.normal(0, 6, n))

    # -- outcome at follow-up -----------------------------------------------------
    outcome = rng.binomial(1, _logistic(
        -1.0 - 0.09 * (measure_3 - 100) + 1.0 * exposure_b + 0.04 * (age - 60)))

    return pd.DataFrame({
        "AGE": age.round(1),
        "SEX": np.where(male == 1, "Male", "Female"),
        "EXPOSURE_A": exposure_a.round(1),
        "EXPOSURE_B": np.where(exposure_b == 1, "Yes", "No"),
        "MEASURE_1": measure_1.round(1),
        "MEASURE_2": measure_2.round(1),
        "MEASURE_3": measure_3.round(1),
        "OUTCOME": np.where(outcome == 1, "Yes", "No"),
    })


#: The arcs used to simulate the cohort, as `(parent, child)` pairs.
TRUE_EDGES: tuple[tuple[str, str], ...] = (
    ("AGE", "EXPOSURE_A"), ("SEX", "EXPOSURE_A"), ("AGE", "EXPOSURE_B"),
    ("AGE", "MEASURE_1"), ("EXPOSURE_A", "MEASURE_1"),
    ("EXPOSURE_A", "MEASURE_2"), ("EXPOSURE_B", "MEASURE_2"),
    ("MEASURE_1", "MEASURE_3"), ("MEASURE_2", "MEASURE_3"),
    ("MEASURE_3", "OUTCOME"), ("EXPOSURE_B", "OUTCOME"), ("AGE", "OUTCOME"),
)
