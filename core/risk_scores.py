"""Cardiovascular risk scores.

Currently just SCORE2 (2021 update). Ported from the R implementation in
RiskScorescvd::SCORE2 and kept intentionally straightforward — a lookup
per (region, sex, age band) followed by the published linear predictor.

Coefficients and calibration constants come from Hageman et al. 2021
(https://doi.org/10.1093/eurheartj/ehab309). Do not tweak them without a
reference — a research reviewer will notice.
"""
from __future__ import annotations

import logging

import numpy as np

LOGGER = logging.getLogger(__name__)

# (age_band, region, sex) -> (calibration_scale1, calibration_scale2)
_CALIBRATION: dict[tuple[str, str, str], tuple[float, float]] = {
    ("under70", "low",       "male"):   (-0.5699, 0.7476),
    ("under70", "low",       "female"): (-0.7380, 0.7019),
    ("under70", "moderate",  "male"):   (-0.1565, 0.8009),
    ("under70", "moderate",  "female"): (-0.3143, 0.7701),
    ("under70", "high",      "male"):   ( 0.3207, 0.9360),
    ("under70", "high",      "female"): ( 0.5710, 0.9369),
    ("under70", "very high", "male"):   ( 0.5836, 0.8294),
    ("under70", "very high", "female"): ( 0.9412, 0.8329),
    ("over70",  "low",       "male"):   (-0.3400, 1.1900),
    ("over70",  "low",       "female"): (-0.5200, 1.0100),
    ("over70",  "moderate",  "male"):   ( 0.0100, 1.2500),
    ("over70",  "moderate",  "female"): (-0.1000, 1.1000),
    ("over70",  "high",      "male"):   ( 0.0800, 1.1500),
    ("over70",  "high",      "female"): ( 0.3800, 1.0900),
    ("over70",  "very high", "male"):   ( 0.0500, 0.7000),
    ("over70",  "very high", "female"): ( 0.3800, 0.6900),
}


def score2(
    *,
    risk_region: str,
    age: float,
    gender: str,
    smoker: float,
    systolic_bp: float,
    diabetes: float,
    total_chol: float,
    total_hdl: float,
    classify: bool = False,
) -> float | str | None:
    """10-year cardiovascular risk for a single patient.

    Parameters
    ----------
    risk_region : {"Low", "Moderate", "High", "Very high"}
        Regional calibration group (Hageman et al. 2021 table 3).
    age, systolic_bp, total_chol, total_hdl : numeric
        Continuous risk factors.
    gender : {"male", "female"}
        Biological sex (SCORE2 has separate equations per sex).
    smoker, diabetes : 0/1
        Binary flags.
    classify : bool, default False
        If True, return a categorical band ("Low risk" / "Moderate risk"
        / "High risk"). Otherwise return the numeric 10-year risk
        percentage rounded to 1 decimal.

    Returns
    -------
    float | str | None
        `None` on missing/unmatchable inputs.
    """
    if not isinstance(gender, str) or gender.lower() not in {"male", "female"}:
        return None
    gender = gender.lower()
    region = risk_region.lower()

    age_band = "under70" if age < 70 else "over70"
    calibration = _CALIBRATION.get((age_band, region, gender))
    if calibration is None:
        LOGGER.warning("SCORE2: unknown region %r; returning None", risk_region)
        return None
    scale1, scale2 = calibration

    smoker = float(smoker) if smoker is not None else 0.0
    diabetes = float(diabetes) if diabetes is not None else 0.0

    risk = _linear_predictor(
        age_band=age_band, gender=gender, age=age, smoker=smoker,
        systolic_bp=systolic_bp, diabetes=diabetes,
        total_chol=total_chol, total_hdl=total_hdl,
        scale1=scale1, scale2=scale2,
    )
    if risk is None or np.isnan(risk):
        return None

    risk_pct = round(risk * 100, 1)
    return _classify(risk_pct, age) if classify else risk_pct


def _linear_predictor(
    *, age_band: str, gender: str, age: float, smoker: float,
    systolic_bp: float, diabetes: float, total_chol: float, total_hdl: float,
    scale1: float, scale2: float,
) -> float | None:
    """Return the SCORE2 10-year risk on the probability scale."""
    if age_band == "under70":
        # baseline survival differs by sex; standardisation uses the "60" pivot
        if gender == "male":
            term = (
                0.3742 * (age - 60) / 5
                + 0.6012 * smoker
                + 0.2777 * (systolic_bp - 120) / 20
                + 0.6457 * diabetes
                + 0.1458 * (total_chol - 6) / 1
                - 0.2698 * (total_hdl - 1.3) / 0.5
                - 0.0755 * (age - 60) / 5 * smoker
                - 0.0255 * (age - 60) / 5 * (systolic_bp - 120) / 20
                - 0.0281 * (age - 60) / 5 * (total_chol - 6) / 1
                + 0.0426 * (age - 60) / 5 * (total_hdl - 1.3) / 0.5
                - 0.0983 * (age - 60) / 5 * diabetes
            )
            baseline_survival = 0.9605
        else:
            term = (
                0.4648 * (age - 60) / 5
                + 0.7744 * smoker
                + 0.3131 * (systolic_bp - 120) / 20
                + 0.8096 * diabetes
                + 0.1002 * (total_chol - 6) / 1
                - 0.2606 * (total_hdl - 1.3) / 0.5
                - 0.1088 * (age - 60) / 5 * smoker
                - 0.0277 * (age - 60) / 5 * (systolic_bp - 120) / 20
                - 0.0226 * (age - 60) / 5 * (total_chol - 6) / 1
                + 0.0613 * (age - 60) / 5 * (total_hdl - 1.3) / 0.5
                - 0.1272 * (age - 60) / 5 * diabetes
            )
            baseline_survival = 0.9776
        tmp = 1 - baseline_survival ** np.exp(term)
        return 1 - np.exp(-np.exp(scale1 + scale2 * np.log(-np.log(1 - tmp))))
    # over 70: pivots at age 73, different baseline survival + shift
    if gender == "male":
        term = (
            0.0634 * (age - 73)
            + 0.4245 * diabetes
            + 0.3524 * smoker
            + 0.0094 * (systolic_bp - 150)
            + 0.0850 * (total_chol - 6)
            - 0.3564 * (total_hdl - 1.4)
            - 0.0174 * (age - 73) * diabetes
            - 0.0247 * (age - 73) * smoker
            - 0.0005 * (age - 73) * (systolic_bp - 150)
            + 0.0073 * (age - 73) * (total_chol - 6)
            + 0.0091 * (age - 73) * (total_hdl - 1.4)
        )
        baseline_survival = 0.7576
        shift = 0.0929
    else:
        term = (
            0.0789 * (age - 73)
            + 0.6010 * diabetes
            + 0.4921 * smoker
            + 0.0102 * (systolic_bp - 150)
            + 0.0605 * (total_chol - 6)
            - 0.3040 * (total_hdl - 1.4)
            - 0.0107 * (age - 73) * diabetes
            - 0.0255 * (age - 73) * smoker
            - 0.0004 * (age - 73) * (systolic_bp - 150)
            - 0.0009 * (age - 73) * (total_chol - 6)
            + 0.0154 * (age - 73) * (total_hdl - 1.4)
        )
        baseline_survival = 0.8082
        shift = 0.2290
    tmp = 1 - baseline_survival ** np.exp(term - shift)
    return 1 - np.exp(-np.exp(scale1 + scale2 * np.log(-np.log(1 - tmp))))


def _classify(risk_pct: float, age: float) -> str:
    """Map a numeric risk percentage to a SCORE2 categorical band."""
    if age < 50:
        thresholds = (2.5, 7.5)
    elif age <= 69:
        thresholds = (5.0, 10.0)
    else:
        thresholds = (7.5, 15.0)
    if risk_pct < thresholds[0]:
        return "Low risk"
    if risk_pct < thresholds[1]:
        return "Moderate risk"
    return "High risk"
