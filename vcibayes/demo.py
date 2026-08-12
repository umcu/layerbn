"""A small synthetic cohort, so the template notebook runs before you have data.

The variable names here are deliberately generic — `MEASUREMENT A`,
`BASELINE TEST SCORE`, `OUTCOME EVENT`. They stand for whatever your cohort
actually measures, and they carry no clinical meaning. A study of cognitive
testing might put MoCA in the outcome layer; a study of imaging might put a
volumetric measure in the measurement layer. Nothing in the package or in the
template notebook refers to any of these names: the spec decides what the
variables are, and everything else reads them from the spec.

What the demo does fix is the *shape* of the problem, because that is what
the method assumes:

* layers in a meaningful order, arcs running downstream through them;
* at least one outcome layer;
* a dropout layer downstream of the outcomes, which is informative here by
  construction, so a complete-case analysis of this cohort would be biased;
* an optional marker layer that can be excluded, to demonstrate an ablation.

    from vcibayes.demo import make_demo_cohort
    df = make_demo_cohort(n=1200, seed=0)

Because the generating structure is known, the demo can show what a
recovered network is supposed to look like. A real cohort cannot.

The data are simulated. They describe no real person and support no
substantive claim.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _logistic(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def make_demo_cohort(n: int = 1200, seed: int = 0) -> pd.DataFrame:
    """Simulate `n` participants from a known layered structure.

    Parameters
    ----------
    n : int
        Number of participants.
    seed : int
        Seed for the random number generator; the same seed gives the same
        cohort.

    Returns
    -------
    DataFrame
        One row per participant, no missing values, matching the variables
        declared in the template spec.

    Notes
    -----
    Effects are larger than a real cohort would show. Structure learning on
    four quantile bins needs a strong signal to recover an arc, and a demo
    whose network came back nearly empty would teach the wrong lesson about
    the method.
    """
    rng = np.random.default_rng(seed)

    # -- Layer 0: demographics --------------------------------------------
    age = rng.normal(70, 8, n).clip(45, 95)
    sex = rng.choice(["Female", "Male"], n)
    male = (sex == "Male").astype(float)
    education = rng.normal(13, 3.2, n).clip(5, 22).round()

    # -- Layer 1: risk factors --------------------------------------------
    risk_score = rng.normal(
        50 + 1.1 * (age - 70) + 6.0 * male - 0.5 * (education - 13), 12, n
    ).clip(0, 100)
    exposure = rng.choice(["None", "Past", "Current"], n, p=[0.45, 0.40, 0.15])
    current_exposure = (exposure == "Current").astype(float)
    comorbidity_count = rng.poisson(
        np.exp(-1.4 + 0.045 * (age - 70) + 0.022 * (risk_score - 50)), n
    ).clip(0, 8)

    # -- Layer 2: optional markers ----------------------------------------
    # Downstream of demographics and risk, upstream of the measurements, and
    # with no direct arc to either outcome. Excluding this layer should
    # therefore leave the outcome structure essentially unchanged, which is
    # what the ablation section of the template notebook demonstrates.
    marker_1 = np.exp(
        rng.normal(2.5 + 0.035 * (age - 70) + 0.15 * comorbidity_count, 0.30, n)
    ).clip(1, 200)
    marker_2 = np.exp(rng.normal(0.9 + 0.022 * (age - 70), 0.32, n)).clip(0.1, 40)

    # -- Layer 3: measurements --------------------------------------------
    measurement_a = np.exp(
        rng.normal(
            0.50 + 0.126 * (age - 70) + 0.028 * (risk_score - 50)
            + 0.30 * comorbidity_count + 0.011 * (marker_1 - 12),
            0.35, n,
        )
    ).clip(0.1, 60)
    measurement_b = rng.normal(
        3.55 - 0.031 * (age - 70) - 0.056 * measurement_a - 0.196 * male, 0.22, n
    ).clip(1.8, 5.0)

    # -- Layer 4: baseline function ---------------------------------------
    baseline_test = rng.normal(
        28.6 - 0.098 * (age - 70) - 0.126 * measurement_a
        + 1.54 * (measurement_b - 3.5) + 0.10 * (education - 13),
        1.0, n,
    ).clip(6, 30).round()

    # -- Layer 5: outcomes -------------------------------------------------
    decline = rng.binomial(1, _logistic(
        -1.2 + 0.098 * (age - 70) + 0.126 * measurement_a
        - 1.68 * (measurement_b - 3.5) - 0.63 * (baseline_test - 28)
    ))
    event = rng.binomial(1, _logistic(
        -2.0 + 0.084 * (age - 70) + 0.042 * (risk_score - 50)
        + 0.55 * comorbidity_count + 1.26 * current_exposure + 0.84 * male
    ))

    # -- Layer 6: dropout, informative by construction ---------------------
    # Participants who decline or have an event are likelier to be lost, so
    # who remains observed depends on the outcomes. The selection layer is
    # what lets the network represent that rather than assume it away.
    dropped = rng.binomial(1, _logistic(
        -2.0 + 0.07 * (age - 70) + 1.82 * decline + 2.10 * event
    )).astype(bool)
    reason = np.where(
        dropped,
        rng.choice(["Died", "Withdrew", "Lost to follow-up"], n, p=[0.3, 0.4, 0.3]),
        "Completed",
    )

    return pd.DataFrame({
        "AGE": age.round(1),
        "SEX": sex,
        "EDUCATION YEARS": education,
        "RISK SCORE": risk_score.round(1),
        "EXPOSURE": exposure,
        "COMORBIDITY COUNT": comorbidity_count,
        "MARKER 1": marker_1.round(2),
        "MARKER 2": marker_2.round(3),
        "MEASUREMENT A": measurement_a.round(2),
        "MEASUREMENT B": measurement_b.round(3),
        "BASELINE TEST SCORE": baseline_test,
        "OUTCOME DECLINE": np.where(decline == 1, "Yes", "No"),
        "OUTCOME EVENT": np.where(event == 1, "Yes", "No"),
        "DROPOUT REASON": reason,
    })


#: The arcs used to simulate the cohort, as `(parent, child)` pairs.
#: The template notebook compares the learned structure against these, which
#: is only possible because the data are synthetic.
TRUE_EDGES: tuple[tuple[str, str], ...] = (
    ("AGE", "RISK SCORE"),
    ("SEX", "RISK SCORE"),
    ("EDUCATION YEARS", "RISK SCORE"),
    ("AGE", "COMORBIDITY COUNT"),
    ("RISK SCORE", "COMORBIDITY COUNT"),
    ("AGE", "MARKER 1"),
    ("COMORBIDITY COUNT", "MARKER 1"),
    ("AGE", "MARKER 2"),
    ("AGE", "MEASUREMENT A"),
    ("RISK SCORE", "MEASUREMENT A"),
    ("COMORBIDITY COUNT", "MEASUREMENT A"),
    ("MARKER 1", "MEASUREMENT A"),
    ("AGE", "MEASUREMENT B"),
    ("SEX", "MEASUREMENT B"),
    ("MEASUREMENT A", "MEASUREMENT B"),
    ("AGE", "BASELINE TEST SCORE"),
    ("EDUCATION YEARS", "BASELINE TEST SCORE"),
    ("MEASUREMENT A", "BASELINE TEST SCORE"),
    ("MEASUREMENT B", "BASELINE TEST SCORE"),
    ("AGE", "OUTCOME DECLINE"),
    ("MEASUREMENT A", "OUTCOME DECLINE"),
    ("MEASUREMENT B", "OUTCOME DECLINE"),
    ("BASELINE TEST SCORE", "OUTCOME DECLINE"),
    ("AGE", "OUTCOME EVENT"),
    ("SEX", "OUTCOME EVENT"),
    ("RISK SCORE", "OUTCOME EVENT"),
    ("COMORBIDITY COUNT", "OUTCOME EVENT"),
    ("EXPOSURE", "OUTCOME EVENT"),
    ("AGE", "DROPOUT REASON"),
    ("OUTCOME DECLINE", "DROPOUT REASON"),
    ("OUTCOME EVENT", "DROPOUT REASON"),
)
