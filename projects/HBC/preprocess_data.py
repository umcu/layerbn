#!/usr/bin/env python3
"""Recreate the 01-A.R preprocessing pipeline in Python.

This script loads the raw HART-BREIN data, engineers the clinical outcomes,
creates the metadata table that enforces the expert-defined layers, and writes
the `df.parquet`, `df_imp.parquet`, and `bn_vars.parquet` artefacts consumed by
`projects/HBC/01_bayesian_network.ipynb`.

Usage
-----
python projects/HBC/preprocess_data.py --project-root /path/to/project --risk-region Low

The defaults assume the following layout relative to the project root::

    data/
      raw/
        df.sav
        fu_2.sav
        compound_score.xlsx
        cs_cleaned_final.csv
      meta/
        HBC_CODEBOOK_LABELS.xlsx

Dependencies
------------
- pandas >= 2
- numpy
- pyreadstat  (for SPSS .sav files)
- scikit-learn (IterativeImputer)
"""
from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import yaml
import pandas as pd
import re
from pandas.api.types import CategoricalDtype
import pyreadstat
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer


LOGGER = logging.getLogger(__name__)


@dataclass
class PreprocessConfig:
    """Configuration for the preprocessing run."""

    project_root: Path
    risk_region: str = "Low"
    raw_dir: Path | None = None
    output_dir: Path | None = None
    codebook_path: Path | None = None
    seed: int = 1234

    def __post_init__(self) -> None:
        self.project_root = self.project_root.resolve()
        self.raw_dir = (self.project_root / "data" / "raw") if self.raw_dir is None else self.raw_dir
        self.output_dir = (self.project_root / "data") if self.output_dir is None else self.output_dir
        default_codebook = self.project_root / "data" / "meta" / "HBC_CODEBOOK_LABELS.xlsx"
        self.codebook_path = default_codebook if self.codebook_path is None else self.codebook_path

    def apply_overrides(self, overrides: Mapping[str, str]) -> None:
        def _as_path(value: str | None) -> Path | None:
            if value in (None, ""):
                return None
            path = Path(value)
            if not path.is_absolute():
                path = (self.project_root / path).resolve()
            return path

        if not overrides:
            return
        if "risk_region" in overrides:
            self.risk_region = str(overrides["risk_region"])
        if "raw_dir" in overrides:
            self.raw_dir = _as_path(overrides["raw_dir"]) or self.raw_dir
        if "output_dir" in overrides:
            self.output_dir = _as_path(overrides["output_dir"]) or self.output_dir
        if "codebook_path" in overrides:
            self.codebook_path = _as_path(overrides["codebook_path"]) or self.codebook_path


# ---------------------------------------------------------------------------
# SCORE2 port (translated from RiskScorescvd::SCORE2)
# ---------------------------------------------------------------------------

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
    """Compute SCORE2 cardiovascular risk for a single patient."""

    gender = gender.lower() if isinstance(gender, str) else gender
    if gender not in {"male", "female"}:
        return None

    scale1 = scale2 = None
    rr = risk_region.lower()
    if age < 70:
        if rr == "low" and gender == "male":
            scale1, scale2 = -0.5699, 0.7476
        elif rr == "low" and gender == "female":
            scale1, scale2 = -0.738, 0.7019
        elif rr == "moderate" and gender == "male":
            scale1, scale2 = -0.1565, 0.8009
        elif rr == "moderate" and gender == "female":
            scale1, scale2 = -0.3143, 0.7701
        elif rr == "high" and gender == "male":
            scale1, scale2 = 0.3207, 0.936
        elif rr == "high" and gender == "female":
            scale1, scale2 = 0.571, 0.9369
        elif rr == "very high" and gender == "male":
            scale1, scale2 = 0.5836, 0.8294
        elif rr == "very high" and gender == "female":
            scale1, scale2 = 0.9412, 0.8329
    else:
        if rr == "low" and gender == "male":
            scale1, scale2 = -0.34, 1.19
        elif rr == "low" and gender == "female":
            scale1, scale2 = -0.52, 1.01
        elif rr == "moderate" and gender == "male":
            scale1, scale2 = 0.01, 1.25
        elif rr == "moderate" and gender == "female":
            scale1, scale2 = -0.1, 1.1
        elif rr == "high" and gender == "male":
            scale1, scale2 = 0.08, 1.15
        elif rr == "high" and gender == "female":
            scale1, scale2 = 0.38, 1.09
        elif rr == "very high" and gender == "male":
            scale1, scale2 = 0.05, 0.7
        elif rr == "very high" and gender == "female":
            scale1, scale2 = 0.38, 0.69
    if scale1 is None or scale2 is None:
        LOGGER.warning("Risk region specification required for SCORE2 computation; returning None")
        return None

    smoker = float(smoker) if smoker is not None else 0.0
    diabetes = float(diabetes) if diabetes is not None else 0.0

    def _calc_under70() -> float:
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
            tmp = 1 - 0.9605 ** np.exp(term)
            return 1 - np.exp(-np.exp(scale1 + scale2 * np.log(-np.log(1 - tmp))))
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
            tmp = 1 - 0.9776 ** np.exp(term)
            return 1 - np.exp(-np.exp(scale1 + scale2 * np.log(-np.log(1 - tmp))))

    def _calc_over70() -> float:
        if gender == "male":
            term = (
                0.0634 * (age - 73)
                + 0.4245 * diabetes
                + 0.3524 * smoker
                + 0.0094 * (systolic_bp - 150)
                + 0.085 * (total_chol - 6)
                - 0.3564 * (total_hdl - 1.4)
                - 0.0174 * (age - 73) * diabetes
                - 0.0247 * (age - 73) * smoker
                - 0.0005 * (age - 73) * (systolic_bp - 150)
                + 0.0073 * (age - 73) * (total_chol - 6)
                + 0.0091 * (age - 73) * (total_hdl - 1.4)
            )
            tmp = 1 - 0.7576 ** np.exp(term - 0.0929)
            return 1 - np.exp(-np.exp(scale1 + scale2 * np.log(-np.log(1 - tmp))))
        else:
            term = (
                0.0789 * (age - 73)
                + 0.601 * diabetes
                + 0.4921 * smoker
                + 0.0102 * (systolic_bp - 150)
                + 0.0605 * (total_chol - 6)
                - 0.304 * (total_hdl - 1.4)
                - 0.0107 * (age - 73) * diabetes
                - 0.0255 * (age - 73) * smoker
                - 0.0004 * (age - 73) * (systolic_bp - 150)
                - 0.0009 * (age - 73) * (total_chol - 6)
                + 0.0154 * (age - 73) * (total_hdl - 1.4)
            )
            tmp = 1 - 0.8082 ** np.exp(term - 0.229)
            return 1 - np.exp(-np.exp(scale1 + scale2 * np.log(-np.log(1 - tmp))))

    risk = _calc_under70() if age < 70 else _calc_over70()
    if np.isnan(risk):
        return None
    risk_pct = round(risk * 100, 1)

    if classify:
        if age < 50:
            if risk_pct < 2.5:
                return "Low risk"
            if risk_pct < 7.5:
                return "Moderate risk"
            return "High risk"
        if age <= 69:
            if risk_pct < 5:
                return "Low risk"
            if risk_pct < 10:
                return "Moderate risk"
            return "High risk"
        if risk_pct < 7.5:
            return "Low risk"
        if risk_pct < 15:
            return "Moderate risk"
        return "High risk"
    return risk_pct


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def read_sav(path: Path) -> tuple[pd.DataFrame, object]:
    if not path.exists():
        raise FileNotFoundError(path)
    return pyreadstat.read_sav(path)



def apply_value_labels(df: pd.DataFrame, meta) -> pd.DataFrame:
    """Replace numeric codes with SPSS value labels when available."""
    if meta is None or not getattr(meta, "value_labels", None):
        return df

    result = df.copy()
    value_sets = meta.value_labels
    variable_map = getattr(meta, "variable_value_labels", {})

    for column, label_set in variable_map.items():
        if column not in result.columns:
            continue
        if isinstance(label_set, dict):
            mapping = label_set
        else:
            mapping = value_sets.get(label_set, {})
        if mapping:
            result[column] = result[column].replace(mapping)
    return result

def coalesce(df: pd.DataFrame, cols: Sequence[str], target: str) -> None:
    """Replicate dplyr::coalesce behaviour across multiple columns."""

    series = None
    for col in cols:
        if col not in df:
            continue
        series = df[col] if series is None else series.fillna(df[col])
    if series is not None:
        df[target] = series


def to_datetime(df: pd.DataFrame, columns: Iterable[str]) -> None:
    for col in columns:
        if col in df:
            df[col] = pd.to_datetime(df[col], errors="coerce")


def map_cdr_values(series: pd.Series) -> pd.Series:
    mapping = {1: 0.5, 2: 1.0, 3: 2.0, 4: 3.0}
    return series.replace(mapping)


def build_outcomes(df_fu: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reproduce the outcome derivations from 01-A.R."""

    outcome_cols = [
        "patientID",
        "T0_datumbaselinebezoek_E1_C1",
        "T2_datumfu2bezoek_E3_C10",
        "T4_datum_tel_int_E4_C12",
        "T0_CDR_E1_C1",
        "T2_CDR_E3_C10",
        "T2_CDR_E3_C11",
        "T4_CDR_E4_C12",
        "T2_reden_geen_deelname_E3_C11",
        "T4_reden_geen_deelname_E4_C12",
        "T0_CVA_E1_C1",
        "T0_hartinfarct_E1_C1",
        "T0_dotter_E1_C1",
        "T0_dotter_stent_E1_C1",
        "T0_bypass_E1_C1",
        "T0_etalagebenen_E1_C1",
        "T0_TIA_E1_C1",
        "T2_CVA_E3_C10",
        "T2_CVA_E3_C11",
        "T2_CVA_datum_E3_C10",
        "T2_CVA_datum_E3_C11",
        "T2_CVA_type_E3_C10",
        "T2_CVA_type_E3_C11",
        "T2_CVA_type_overig_E3_C10",
        "T2_CVA_type_overig_E3_C11",
        "T2_cardio_E3_C10",
        "T2_cardio_E3_C11",
        "T2_cardio_type_E3_C10",
        "T2_cardio_type_E3_C11",
        "T2_cardio_type_overig_E3_C10",
        "T2_cardio_type_overig_E3_C11",
        "T2_cardio_datum_E3_C10",
        "T2_cardio_datum_E3_C11",
        "T2_1_datum_overlijden_E3_C11",
        "T2_1_oorzaak_overlijden_E3_C11",
        "T4_CVA_E4_C12",
        "T4_CVA_datum_E4_C12",
        "T4_CVA_type_overig_E4_C12",
        "T4_cardio_E4_C12",
        "T4_cardio_type_E4_C12",
        "T4_cardio_type_overig_E4_C12",
        "T4_cardio_datum_E4_C12",
        "T4_1_datum_overlijden_E4_C12",
        "T4_1_oorzaak_overlijden_E4_C12",
    ]
    essential_cols = {"patientID", "T0_CDR_E1_C1", "T2_CDR_E3_C10", "T4_CDR_E4_C12"}
    missing_essential = [c for c in essential_cols if c not in df_fu]
    if missing_essential:
        raise KeyError(f"Essential outcome columns missing from fu dataset: {missing_essential}")
    missing_optional = [c for c in outcome_cols if c not in df_fu]
    if missing_optional:
        LOGGER.warning("Outcome columns missing from fu dataset and will be filled with NaN: %s", missing_optional)

    outcomes = df_fu.reindex(columns=outcome_cols)
    date_cols = [c for c in outcomes.columns if "datum" in c.lower()]
    to_datetime(outcomes, date_cols)

    outcomes.rename(
        columns={
            "T0_CDR_E1_C1": "T0_CDR",
            "T2_CDR_E3_C10": "T2_CDR",
            "T4_CDR_E4_C12": "T4_CDR",
        },
        inplace=True,
    )
    for col in ['T0_CDR', 'T2_CDR', 'T4_CDR']:
        if col in outcomes:
            outcomes[col] = pd.to_numeric(outcomes[col], errors='coerce')
    outcomes["T4_CDR"] = map_cdr_values(outcomes.get("T4_CDR", pd.Series(dtype=float, index=outcomes.index)))
    outcomes["T2_CDR"] = map_cdr_values(outcomes.get("T2_CDR", pd.Series(dtype=float, index=outcomes.index)))

    # Coalesce duplicated follow-up columns
    coalesce(outcomes, ["T2_CVA_E3_C10", "T2_CVA_E3_C11"], "T2_CVA")
    coalesce(outcomes, ["T2_CVA_type_E3_C10", "T2_CVA_type_E3_C11"], "T2_CVA_type")
    coalesce(outcomes, ["T2_CVA_datum_E3_C10", "T2_CVA_datum_E3_C11"], "T2_CVA_datum")
    coalesce(outcomes, ["T2_cardio_E3_C10", "T2_cardio_E3_C11"], "T2_cardio")
    coalesce(outcomes, ["T2_cardio_type_E3_C10", "T2_cardio_type_E3_C11"], "T2_cardio_type")
    coalesce(outcomes, ["T2_cardio_type_overig_E3_C10", "T2_cardio_type_overig_E3_C11"], "T2_cardio_type_overig")
    coalesce(outcomes, ["T2_cardio_datum_E3_C10", "T2_cardio_datum_E3_C11"], "T2_cardio_datum")

    # Drop original duplicates
    drop_cols = [
        "T2_CDR_E3_C11",
        "T2_CVA_E3_C10",
        "T2_CVA_E3_C11",
        "T2_CVA_type_E3_C10",
        "T2_CVA_type_E3_C11",
        "T2_CVA_datum_E3_C10",
        "T2_CVA_datum_E3_C11",
        "T2_cardio_E3_C10",
        "T2_cardio_E3_C11",
        "T2_cardio_type_E3_C10",
        "T2_cardio_type_E3_C11",
        "T2_cardio_type_overig_E3_C10",
        "T2_cardio_type_overig_E3_C11",
        "T2_cardio_datum_E3_C10",
        "T2_cardio_datum_E3_C11",
    ]
    outcomes.drop(columns=[c for c in drop_cols if c in outcomes], inplace=True)

    # Stroke events
    t0_cva = pd.to_numeric(outcomes.get("T0_CVA_E1_C1"), errors="coerce")
    outcomes["T0_Event_Stroke"] = np.where(t0_cva.isin([1, 2, 3]), 1, 0)

    def contains_any(series: pd.Series, patterns: Sequence[str]) -> pd.Series:
        pattern = "|".join(patterns)
        return series.fillna('').str.contains(pattern, case=False, regex=True)

    outcomes["T2_Event_Stroke"] = np.where(
        outcomes["T2_CVA"].isin([1, 2])
        | contains_any(outcomes.get("T2_1_oorzaak_overlijden_E3_C11"), ["cva", "herseninfarct", "hersenbloeding"]),
        1,
        0,
    )
    outcomes["T4_Event_Stroke"] = np.where(
        outcomes["T4_CVA_E4_C12"].isin([1, 2])
        | contains_any(outcomes.get("T4_1_oorzaak_overlijden_E4_C12"), ["cva", "herseninfarct", "hersenbloeding"]),
        1,
        0,
    )
    outcomes["Event_Stroke"] = np.where(
        (outcomes["T2_Event_Stroke"] == 1) | (outcomes["T4_Event_Stroke"] == 1),
        1,
        0,
    )

    # MACE definition
    mace_baseline = (
        outcomes["T0_CVA_E1_C1"].isin([1, 2, 3])
        | (outcomes.get("T0_hartinfarct_E1_C1") == 1)
        | (outcomes.get("T0_dotter_E1_C1") == 1)
        | (outcomes.get("T0_dotter_stent_E1_C1") == 1)
        | (outcomes.get("T0_bypass_E1_C1") == 1)
        | (outcomes.get("T0_etalagebenen_E1_C1") == 1)
    )
    outcomes["T0_Event_MACE"] = np.where(mace_baseline, 1, 0)

    def has_event(series):
        if series is None:
            return pd.Series(False, index=outcomes.index)
        if pd.api.types.is_numeric_dtype(series):
            return series.isin([1, 2])
        series_str = series.astype(str).str.strip().str.casefold()
        return series_str.str.startswith('ja')

    mace_t2 = (
        has_event(outcomes.get('T2_CVA'))
        | has_event(outcomes.get('T2_cardio'))
        | contains_any(outcomes.get('T2_1_oorzaak_overlijden_E3_C11'), [
            'myocardinfarct',
            'hersenbloeding',
            'aneurysma',
        ])
    )
    outcomes['T2_Event_MACE'] = np.where(mace_t2, 1, 0)

    mace_t4 = (
        has_event(outcomes.get('T4_CVA_E4_C12'))
        | has_event(outcomes.get('T4_cardio_E4_C12'))
        | contains_any(outcomes.get('T4_1_oorzaak_overlijden_E4_C12'), [
            'cva',
            'herseninfarct',
            'vaatlijden',
            'subarach',
            'hartstilstand',
            'cardiac arrest',
            'decompensatio',
            'hartfalen',
            'vasculaire',
            'myocardinfarct',
        ])
    )
    outcomes['T4_Event_MACE'] = np.where(mace_t4, 1, 0)
    outcomes['OUTCOME_MACE'] = np.where(
        (outcomes['T2_Event_MACE'] == 1) | (outcomes['T4_Event_MACE'] == 1),
        1,
        0,
    )

    # Dropout reasons
    dropout_labels = {
        0: 'Untraceable',
        1: 'Deceased',
        2: 'Too Ill',
        3: 'Moved to Nursing Home',
        4: 'Refusal',
        5: 'Other',
    }
    canonical_dropout = {
        'no dropout': 'No Dropout',
        'untraceerbaar': 'Untraceable',
        'untraceable': 'Untraceable',
        'deceased': 'Deceased',
        'too ill': 'Too Ill',
        'moved to nursing home': 'Moved to Nursing Home',
        'refusal': 'Refusal',
        'other': 'Other',
    }
    for phase in ('T2', 'T4'):
        col = f"{phase}_reden_geen_deelname_E3_C11" if phase == 'T2' else 'T4_reden_geen_deelname_E4_C12'
        new_col = f"{phase}_dropout_reason"
        series = outcomes.get(col)
        if series is None:
            outcomes[new_col] = 'No Dropout'
            outcomes[f"{new_col}_norm"] = 'no dropout'
            continue
        if pd.api.types.is_numeric_dtype(series):
            mapped = series.map(dropout_labels)
        else:
            mapped = series.replace(dropout_labels)
        filled = mapped.fillna(series).fillna('No Dropout')

        def _translate_dropout(value: str) -> str:
            if not isinstance(value, str):
                return value
            val = value.strip()
            if not val:
                return 'No Dropout'
            match = re.match(r'^([0-9])\s*=\s*(.*)$', val)
            if match:
                num_code = int(match.group(1))
                remainder = match.group(2).strip()
                return dropout_labels.get(num_code, canonical_dropout.get(remainder.casefold(), remainder))
            lower = val.casefold()
            replacements = {
                'geen dropout': 'No Dropout',
                'geendropout': 'No Dropout',
                'no dropout': 'No Dropout',
                'ontraceerbaar': 'Untraceable',
                'patiënt is overleden': 'Deceased',
                'patiënt is te ziek': 'Too Ill',
                'patiënt is opgenomen in een verzorgingshuis': 'Moved to Nursing Home',
                'patiënt is opgenomen in een verzorgingshuis/verpleeghuis': 'Moved to Nursing Home',
                'patiënt is opgenomen in een verzorgingshuis / verpleeghuis': 'Moved to Nursing Home',
                'patiënt weigert': 'Refusal',
                'deelnemer, naaste en (huis)arts kunnen niet worden getraceerd': 'Untraceable',
                'deelnemer kan niet worden getraceerd': 'Untraceable',
                'deelnemer is overleden': 'Deceased',
                'deelnemer is te ziek': 'Too Ill',
                'deelnemer is opgenomen in een verzorgingshuis/verpleeghuis': 'Moved to Nursing Home',
                'deelnemer is opgenomen in een verzorgingshuis / verpleeghuis': 'Moved to Nursing Home',
                'deelnemer weigert': 'Refusal',
                'anders, namelijk': 'Other',
                'anders': 'Other',
            }
            for key, replacement in replacements.items():
                if lower.startswith(key):
                    return replacement
            return canonical_dropout.get(lower, val)

        translated = filled.apply(_translate_dropout)
        outcomes[new_col] = translated
        outcomes[f"{new_col}_norm"] = translated.astype(str).str.strip().str.casefold()

    outcomes["OUTCOME_CDR_INCREASE"] = np.where(
        (outcomes["T2_CDR"] > outcomes["T0_CDR"])
        | (outcomes["T4_CDR"] > outcomes["T0_CDR"])
        | (outcomes["T4_CDR"] > outcomes["T2_CDR"])
        | (outcomes["T2_dropout_reason"] == "Moved to Nursing Home")
        | (outcomes["T4_dropout_reason"] == "Moved to Nursing Home"),
        1,
        0,
    )

    outcomes.loc[
        outcomes["OUTCOME_CDR_INCREASE"].isna() & (outcomes["T4_CDR"] > outcomes["T0_CDR"]),
        "OUTCOME_CDR_INCREASE",
    ] = 1
    # Convert outcomes into categorical labels with explicit Unobserved state
    mask_mace_unobserved = (outcomes["OUTCOME_MACE"] == 0) & (outcomes.get('T4_dropout_reason_norm', outcomes['T4_dropout_reason'].astype(str).str.strip().str.casefold()) != 'no dropout')
    outcomes.loc[mask_mace_unobserved, "OUTCOME_MACE"] = np.nan
    outcomes["OUTCOME_MACE"] = outcomes["OUTCOME_MACE"].map({1: "Yes", 0: "No"}).fillna("Unobserved").astype("category")

    mask_cdr_unobserved = outcomes["OUTCOME_CDR_INCREASE"].isna() | ((outcomes["OUTCOME_CDR_INCREASE"] == 0) & (outcomes.get('T4_dropout_reason_norm', outcomes['T4_dropout_reason'].astype(str).str.strip().str.casefold()) != 'no dropout'))
    outcomes.loc[mask_cdr_unobserved, "OUTCOME_CDR_INCREASE"] = np.nan
    outcomes["OUTCOME_CDR_INCREASE"] = outcomes["OUTCOME_CDR_INCREASE"].map({1: "Yes", 0: "No"}).fillna("Unobserved").astype("category")

    norm_cols = [col for col in outcomes.columns if col.endswith('_dropout_reason_norm')]
    outcomes.drop(columns=norm_cols, inplace=True)

    outcomes_sub = outcomes[["patientID", "T4_dropout_reason", "OUTCOME_MACE", "OUTCOME_CDR_INCREASE"]].copy()

    return outcomes, outcomes_sub


def prepare_subset(df_fu: pd.DataFrame, bn_vars: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    bn_vars_filter = bn_vars.loc[bn_vars["LAYER"].notna(), ["LAYER", "VARIABLE NAME"]].copy()
    bn_vars_filter.loc[bn_vars_filter["VARIABLE NAME"] == "DROPOUT REASON", "LAYER"] = "L9 – Dropout"
    extra_vars = [
        "patientID",
        "T0_patientengroep_E1_C1",
        "Sex",
        "T0_Age",
        "T0_pTau181",
        "T0_NfL",
        "T0_GFAP",
        "T0_Aβ40",
        "T0_Aβ42",
    ]

    all_cols = pd.Index(df_fu.columns)
    base_names = all_cols.str.replace(r"_E[0-9]+_C[0-9]+$", "", regex=True)
    allowed = bn_vars_filter["VARIABLE NAME"].unique()
    matched_cols = [col for col, base in zip(all_cols, base_names) if base in allowed]
    final_cols = list(dict.fromkeys(extra_vars + matched_cols))
    subset = df_fu.loc[:, [c for c in final_cols if c in df_fu]].copy()

    def safe_mean(cols: Sequence[str]) -> pd.Series:
        present = [subset[c] for c in cols if c in subset]
        if not present:
            return pd.Series(np.nan, index=subset.index)
        return pd.concat(present, axis=1).mean(axis=1, skipna=True)

    subset["T0_SYS_BP"] = safe_mean(["T0_systolisch_a_E1_C1", "T0_systolisch_b_E1_C1"])
    subset["T0_DIAS_BP"] = safe_mean(["T0_Diastolisch_a_E1_C1", "T0_Diastolisch_b_E1_C1"])
    icv = subset.get("T0_q_ic_tissue_total_intracranial_volume_ml")
    if icv is not None:
        subset["T0_HV_ICV"] = safe_mean(["T0_i_ic_gm_Hippocampus_left_volume_ml", "T0_i_ic_gm_Hippocampus_right_volume_ml"]) * 100 / icv
        brain = subset.get("T0_q_ic_tissue_total_brain_volume_ml")
        if brain is not None:
            subset["T0_TBV_ICV"] = brain * 100 / icv
    subset["T0_CBF"] = subset.get("T0_i_ic_cbf_GrayMatter_mean_mL100gmin")

    def fill_smoking(primary: str, backup: str) -> pd.Series:
        res = subset.get(primary, pd.Series(np.nan, index=subset.index)).copy()
        backup_series = subset.get(backup)
        if backup_series is not None:
            res = res.fillna(backup_series)
        return res.fillna(0)

    subset["T0_roken_hoeveel_jaar_a_E1_C1"] = fill_smoking(
        "T0_roken_hoeveel_jaar_a_E1_C1", "T0_roken_hoeveel_jaar_b_E1_C1"
    )
    subset["T0_roken_hoeveel_per_dag_a_E1_C1"] = fill_smoking(
        "T0_roken_hoeveel_per_dag_a_E1_C1", "T0_roken_hoeveel_per_dag_b_E1_C1"
    )

    def is_one(col: str) -> pd.Series:
        series = subset.get(col)
        if series is None:
            return pd.Series(False, index=subset.index)
        series = series.fillna(0)
        if pd.api.types.is_numeric_dtype(series):
            return series == 1
        series_str = series.astype(str).str.strip().str.casefold()
        return series_str.isin({"1", "ja", "yes", "true"})

    subset["T0_CAD"] = np.where(
        is_one("T0_bypass_E1_C1") | is_one("T0_dotter_E1_C1") | is_one("T0_hartinfarct_E1_C1"),
        1,
        0,
    )
    subset["T0_PAD"] = np.where(is_one("T0_etalagebenen_E1_C1"), 1, 0)
    subset["MACE"] = np.where((subset["T0_CAD"] == 1) | (subset["T0_PAD"] == 1), 1, 0)

    subset.drop(
        columns=[
            col
            for col in [
                "T0_roken_hoeveel_jaar_b_E1_C1",
                "T0_roken_hoeveel_per_dag_b_E1_C1",
                "T0_etalagebenen_E1_C1",
                "T0_hartinfarct_E1_C1",
                "T0_bypass_E1_C1",
                "T0_dotter_E1_C1",
                "T0_PAD",
                "T0_CAD",
            ]
            if col in subset
        ],
        inplace=True,
    )

    return subset, bn_vars_filter


def harmonise_columns(df_final: pd.DataFrame, bn_vars_filter: pd.DataFrame) -> None:
    bn_vars_filter["LAYER"] = bn_vars_filter["LAYER"].astype(str).str.strip()
    bn_vars_filter["VARIABLE NAME"] = bn_vars_filter["VARIABLE NAME"].str.replace("T0_", "", regex=False)
    df_final.columns = (
        df_final.columns.str.replace("_E1_C1", "", regex=False)
        .str.replace("_E1_C6", "", regex=False)
        .str.replace("T0_", "", regex=False)
        .str.replace("β", "B", regex=False)
        .str.upper()
    )
    bn_vars_filter["VARIABLE NAME"] = bn_vars_filter["VARIABLE NAME"].str.replace("β", "B", regex=False).str.upper()


EXTRA_LAYER_ROWS = [
    ("L2 – Cardiovascular risk factors", "SYS_BP"),
    ("L2 – Cardiovascular risk factors", "DIAS_BP"),
    ("L5 - Imaging markers of neurovascular damage", "HV_ICV"),
    ("L5 - Imaging markers of neurovascular damage", "TBV_ICV"),
    ("L4 – Potential disease process markers", "CBF"),
    ("L8 – Outcomes", "OUTCOME_CDR_INCREASE"),
    (
        "L9 – Dropout", "DROPOUT REASON"
    ),
    ("L8 – Outcomes", "OUTCOME_MACE"),
    ("L0 – Unmodifiable demographics", "AGE"),
    ("L0 – Unmodifiable demographics", "SEX"),
    ("L4 – Potential disease process markers", "PTAU181"),
    ("L4 – Potential disease process markers", "NFL"),
    ("L4 – Potential disease process markers", "GFAP"),
    ("L6 – Current and previous cardiovascular diagnoses / Vascular interventions", "PATIENTENGROEP"),
    ("L4 – Potential disease process markers", "AB40"),
    ("L4 – Potential disease process markers", "AB42"),
    ("L6 – Current and previous cardiovascular diagnoses / Vascular interventions", "MACE"),
    ("L2 – Cardiovascular risk factors", "SCORE_2"),
]


NAME_MAPPING = {
    "MMSE_TOTAAL": "MINI MENTAL STATE EXAMINATION",
    "STARKSTEIN": "STARKSTEIN SCORE",
    "CDR": "BASELINE CDR",
    "CVA": "STROKE HISTORY",
    "BCS_1": "BIOMARKER SCORE 1",
    "BCS_2": "BIOMARKER SCORE 2",
    "NEURORAD_SVD_SCORE": "SMALL VESSEL DISEASE SCORE",
    "HV_ICV": "HIPPOCAMPUS/INTRACRANIAL VOLUME",
    "TBV_ICV": "BRAIN/INTRACRANIAL VOLUME",
    "CBF": "CEREBRAL BLOOD FLOW",
    "EVENT_MACE": "OUTCOME_MACE",
    "CDR_INCR": "OUTCOME_CDR_INCREASE",
    "T4_DROPOUT_REASON": "DROPOUT REASON",
    "AGE": "AGE",
    "SEX": "SEX",
    "PTAU181": "PTAU181",
    "NFL": "NFL",
    "GFAP": "GFAP",
    "PATIENTENGROEP": "PATIENT GROUP",
    "MACE": "ATHEROSCLEROTIC CARDIOVASCULAR DISEASE HISTORY",
    "SCORE_2": "VASCULAR RISK SCORE",
}


LABEL_TRANSLATION: Mapping[str, Mapping[str, str]] = {
    'STROKE HISTORY': {
        'Ja, hersenbloeding': 'Yes, hemorrhagic stroke',
        'Ja, herseninfarct': 'Yes, ischemic stroke',
        'Ja, type onbekend': 'Yes, type unknown',
        'Nee': 'No',
    },
    'PATIENT GROUP': {
        'Carotid occlusive disease': 'Carotid occlusive disease',
        'Controle': 'Reference',
        'Hartfalen': 'Heart failure',
        'Vascular cognitive impairment': 'Vascular cognitive impairment',
    },
    'ATHEROSCLEROTIC CARDIOVASCULAR DISEASE HISTORY': {'0': 'No', '1': 'Yes'},
}

BASELINE_CDR_CATEGORIES = ['0', '0.5', '1', '1.5', '2', '3']

def enforce_domain_categories(df: pd.DataFrame) -> None:
    if 'BASELINE CDR' in df:
        def _format_cdr(value):
            if pd.isna(value):
                return pd.NA
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return str(value)
            mapping = {0.0: '0', 0.5: '0.5', 1.0: '1', 1.5: '1.5', 2.0: '2', 3.0: '3'}
            return mapping.get(numeric, str(numeric))

        formatted = df['BASELINE CDR'].apply(_format_cdr)
        df['BASELINE CDR'] = pd.Categorical(formatted, categories=BASELINE_CDR_CATEGORIES, ordered=True)

    for column in ['STROKE HISTORY', 'PATIENT GROUP', 'SEX']:
        if column in df:
            series = df[column].astype('string')
            df[column] = pd.Categorical(series, ordered=False)

    if 'ATHEROSCLEROTIC CARDIOVASCULAR DISEASE HISTORY' in df:
        series = df['ATHEROSCLEROTIC CARDIOVASCULAR DISEASE HISTORY'].astype('string').str.strip()
        mapping = {
            '0': 'No',
            '1': 'Yes',
            'No': 'No',
            'Yes': 'Yes',
        }
        translated = series.replace(mapping)
        df['ATHEROSCLEROTIC CARDIOVASCULAR DISEASE HISTORY'] = pd.Categorical(
            translated,
            categories=['No', 'Yes'],
            ordered=False,
        )

def normalise_string_categories(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes(include="object"):
        df[col] = df[col].astype(str).str.strip()
    return df


def translate_labels(df: pd.DataFrame) -> pd.DataFrame:
    for column, mapping in LABEL_TRANSLATION.items():
        if column in df:
            series = df[column].astype(str)
            lower = series.str.strip().str.casefold()
            normalized_mapping = {key.casefold(): value for key, value in mapping.items()}
            mapped = lower.map(normalized_mapping)
            df[column] = series.where(mapped.isna(), mapped)
            df[column] = df[column].astype("category")
    return df


def impute_dataframe(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    numeric = df.select_dtypes(include=["number"]).copy()
    other = df.select_dtypes(exclude=["number"]).copy()

    imputer = IterativeImputer(random_state=seed, sample_posterior=False)
    if not numeric.empty:
        numeric = pd.DataFrame(imputer.fit_transform(numeric), columns=numeric.columns, index=df.index)

    for col in other.columns:
        series = other[col]
        if series.isnull().any():
            if pd.api.types.is_categorical_dtype(series):
                modes = series.mode(dropna=True)
                fill_value = modes.iloc[0] if not modes.empty else series.cat.categories[0]
                if fill_value not in series.cat.categories:
                    series = series.cat.add_categories([fill_value])
                series = series.fillna(fill_value)
            else:
                modes = series.mode(dropna=True)
                fill_value = modes.iloc[0] if not modes.empty else ""
                series = series.fillna(fill_value)
            other[col] = series

    combined = pd.concat([numeric, other], axis=1)
    return combined[df.columns]


BASELINE_GROUP_ORDER = [
    "Carotid occlusive disease",
    "Heart failure",
    "Vascular cognitive impairment",
    "Reference",
]

DIABETES_CATEGORY_LABELS = [
    ("Yes, with lifestyle advice", ["yes, with lifestyle advice", "ja, met leefstijladvies", "ja, met leefstijl advies"]),
    ("Yes, with oral antidiabetics", ["yes, with oral antidiabetics", "ja, met orale antidiabetica", "ja, met orale antidiabetics"]),
    ("Yes, with insulin", ["yes, with insulin", "ja, met insuline"]),
    ("No", ["no", "nee", "geen diabetes"]),
]

SMOKING_CATEGORY_LABELS = [
    ("Yes", ["yes", "ja", "smoker", "current smoker"]),
    ("No", ["no", "nee", "never", "nooit gerookt", "never smoked"]),
    ("Not anymore", ["not anymore", "niet meer", "gestopt", "gestopt met roken", "ex-roker", "ex roker", "ex-smoker", "former smoker", "quit"]),
]

CVA_CATEGORY_LABELS = [
    ("Yes, hemorrhage", ["yes, hemorrhage", "yes, haemorrhage", "yes, hemorrhagic stroke"]),
    ("Yes, stroke", ["yes, stroke", "yes, ischemic stroke"]),
    ("Yes, type unknown", ["yes, type unknown"]),
    ("No", ["no"]),
]

PATIENT_GROUP_CATEGORY_LABELS = [
    ("Carotid occlusive disease", ["carotid occlusive disease"]),
    ("Heart failure", ["heart failure"]),
    ("Vascular cognitive impairment", ["vascular cognitive impairment"]),
    ("Reference", ["reference", "controle"]),
]


def _normalize_label(value: str | float | int | None) -> str | None:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    if isinstance(value, (float, int)) and pd.isna(value):
        return None
    return str(value).strip().casefold()


def _format_median_iqr(series: pd.Series | None) -> str:
    if series is None:
        return "NA"
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return "NA"
    q1 = numeric.quantile(0.25)
    median = numeric.median()
    q3 = numeric.quantile(0.75)
    return f"{median:.2f} [{q1:.2f}, {q3:.2f}]"


def _format_count_pct(series: pd.Series | None, targets: Sequence[str]) -> str:
    if series is None:
        return "NA"
    valid = pd.Series(series).dropna()
    if valid.empty:
        return "NA"
    normalized = valid.apply(_normalize_label).dropna()
    if normalized.empty:
        return "NA"
    target_norms = {_normalize_label(value) for value in targets if value is not None}
    if not target_norms:
        return "NA"
    count = normalized.isin(target_norms).sum()
    pct = (count / len(normalized)) * 100
    return f"{int(count)} ({pct:.1f})"


def _build_group_sequence(df: pd.DataFrame, group_col: str) -> list[tuple[str, pd.DataFrame]]:
    groups: list[tuple[str, pd.DataFrame]] = [("Overall", df)]
    if group_col not in df:
        LOGGER.warning("Baseline table: column %s is missing", group_col)
        return groups
    present_values = df[group_col].dropna()
    added: set[str] = set()
    for label in BASELINE_GROUP_ORDER:
        mask = present_values == label
        if mask.any():
            groups.append((label, df[df[group_col] == label]))
            added.add(label)
    for value in present_values.unique():
        if value in added:
            continue
        groups.append((value, df[df[group_col] == value]))
        added.add(value)
    return groups


def _add_category_rows(
    rows: list[dict[str, str]],
    groups: list[tuple[str, pd.DataFrame]],
    metric_label: str,
    column: str,
    categories: Sequence[tuple[str, Sequence[str]]],
) -> None:
    for display_label, target_values in categories:
        row = {"Metric": metric_label, "Submetric": display_label}
        for group_name, group_df in groups:
            row[group_name] = _format_count_pct(group_df.get(column), target_values)
        rows.append(row)


def build_baseline_table_by_group(df: pd.DataFrame) -> pd.DataFrame:
    """Return baseline characteristics table per patient group."""
    working = df.copy()
    working.rename(columns=NAME_MAPPING, inplace=True)
    working = normalise_string_categories(working)
    working = translate_labels(working)

    group_col = "PATIENT GROUP" if "PATIENT GROUP" in working else "PATIENTENGROEP"
    groups = _build_group_sequence(working, group_col)
    rows: list[dict[str, str]] = []

    def add_simple_row(metric: str, func, submetric: str = "") -> None:
        row = {"Metric": metric, "Submetric": submetric}
        for group_name, group_df in groups:
            row[group_name] = func(group_df)
        rows.append(row)

    add_simple_row("n", lambda gdf: f"{len(gdf)}")
    add_simple_row("Age (median [IQR])", lambda gdf: _format_median_iqr(gdf.get("AGE")))
    add_simple_row(
        "Male sex (%)",
        lambda gdf: _format_count_pct(gdf.get("SEX"), ["male", "man", "m"]),
    )

    _add_category_rows(rows, groups, "Diabetes (%)", "DIABETES", DIABETES_CATEGORY_LABELS)
    _add_category_rows(rows, groups, "Smoking (%)", "ROKEN", SMOKING_CATEGORY_LABELS)

    add_simple_row(
        "Systolic blood pressure (median [IQR])",
        lambda gdf: _format_median_iqr(gdf.get("SYS_BP")),
    )
    add_simple_row(
        "Low-density lipoprotein cholesterol (median [IQR])",
        lambda gdf: _format_median_iqr(gdf.get("CHOLESTEROL_LDL")),
    )
    add_simple_row(
        "Systematic Coronary Risk Evaluation score (median [IQR])",
        lambda gdf: _format_median_iqr(gdf.get("SCORE_2")),
    )
    add_simple_row(
        "Blood pressure medication = No (%)",
        lambda gdf: _format_count_pct(gdf.get("BLOEDDRUK_MEDICATIE"), ["no", "nee", "0"]),
    )
    add_simple_row(
        "Transient Ischaemic Attack = No (%)",
        lambda gdf: _format_count_pct(gdf.get("TIA"), ["no", "nee", "0"]),
    )

    _add_category_rows(
        rows,
        groups,
        "Cerebrovascular Accident (%)",
        "STROKE HISTORY",
        CVA_CATEGORY_LABELS,
    )
    _add_category_rows(
        rows,
        groups,
        "Patient group (%)",
        group_col,
        PATIENT_GROUP_CATEGORY_LABELS,
    )

    table = pd.DataFrame(rows)
    group_names = [name for name, _ in groups]
    ordered_cols = ["Metric", "Submetric"] + group_names
    return table.loc[:, ordered_cols]


def preprocess(config: PreprocessConfig) -> None:
    LOGGER.info("Loading raw tables from %s", config.raw_dir)
    df_bl, meta_bl = read_sav(config.raw_dir / "df.sav")
    df_bl = apply_value_labels(df_bl, meta_bl)
    df_fu, meta_fu = read_sav(config.raw_dir / "fu_2.sav")
    df_fu = apply_value_labels(df_fu, meta_fu)
    cs_1 = pd.read_excel(config.raw_dir / "compound_score.xlsx")
    cs_2 = pd.read_csv(config.raw_dir / "cs_cleaned_final.csv", sep=";", decimal=",")

    for frame in (cs_1, cs_2):
        if "patientID" in frame:
            frame["patientID"] = pd.to_numeric(frame["patientID"], errors="coerce")

    df_fu = df_fu.merge(cs_1, how="left", on="patientID").merge(cs_2, how="left", on="patientID")

    outcomes, outcomes_sub = build_outcomes(df_fu)

    bn_vars = pd.read_excel(config.codebook_path, sheet_name="Items")
    bn_vars.loc[bn_vars["VARIABLE NAME"] == "DROPOUT REASON", "LAYER"] = "L9 – Dropout"
    subset, bn_vars_filter = prepare_subset(df_fu, bn_vars)

    df_final = subset.merge(outcomes_sub, how="left", on="patientID")
    harmonise_columns(df_final, bn_vars_filter)

    extra = pd.DataFrame(EXTRA_LAYER_ROWS, columns=["LAYER", "VARIABLE NAME"])
    extra.loc[extra['VARIABLE NAME'] == 'DROPOUT REASON', 'LAYER'] = 'L9 – Dropout'
    bn_vars_filter = pd.concat([bn_vars_filter, extra], ignore_index=True)
    bn_vars_filter.loc[bn_vars_filter["VARIABLE NAME"] == "DROPOUT REASON", "LAYER"] = "L9 – Dropout"
    bn_vars_filter = bn_vars_filter.drop_duplicates(subset=["VARIABLE NAME"])

    df_final = normalise_string_categories(df_final)

    # Convert labelled columns using the metadata stored by pyreadstat
    df_final = df_final.apply(lambda col: col.astype(str).str.title() if col.dtype == object else col)

    df_clean_score = df_final.copy()
    sex_series = df_clean_score.get("SEX")
    if sex_series is not None:
        sex_lower = sex_series.astype(str).str.lower()
    else:
        sex_lower = pd.Series("male", index=df_clean_score.index)
    df_clean_score["SEX_SCORE"] = np.where(sex_lower == "female", "female", "male")

    df_clean_score["ROKEN_SCORE"] = np.where(
        df_clean_score.get("ROKEN", pd.Series("Nee", index=df_clean_score.index)) == "Ja",
        1,
        0,
    )
    df_clean_score["DIABETES_SCORE"] = np.where(
        df_clean_score.get("DIABETES", pd.Series("Ja", index=df_clean_score.index)) == "Nee",
        0,
        1,
    )

    def row_score(row: pd.Series) -> float | None:
        try:
            return score2(
                risk_region=config.risk_region,
                age=float(row.get("AGE")),
                gender=row.get("SEX_SCORE", "male"),
                smoker=float(row.get("ROKEN_SCORE", 0)),
                systolic_bp=float(row.get("SYS_BP")),
                diabetes=float(row.get("DIABETES_SCORE", 0)),
                total_chol=float(row.get("CHOLESTEROL_TOTAAL")),
                total_hdl=float(row.get("CHOLESTEROL_HDL")),
            )
        except (TypeError, ValueError):
            return None

    df_clean_score["SCORE_2"] = df_clean_score.apply(row_score, axis=1)

    reduced_cols = [
        "AGE",
        "SEX",
        "PTAU181",
        "NFL",
        "GFAP",
        "AB40",
        "AB42",
        "MMSE_TOTAAL",
        "STARKSTEIN",
        "CDR",
        "CVA",
        "NEURORAD_SVD_SCORE",
        "BCS_1",
        "BCS_2",
        "HV_ICV",
        "TBV_ICV",
        "CBF",
        "MACE",
        "OUTCOME_MACE",
        "OUTCOME_CDR_INCREASE",
        "T4_DROPOUT_REASON",
        "SCORE_2",
        "PATIENTENGROEP",
    ]
    df_clean_reduced = df_clean_score[[c for c in reduced_cols if c in df_clean_score]].copy()

    bn_vars_filter_2 = bn_vars_filter[bn_vars_filter["VARIABLE NAME"].isin(df_clean_reduced.columns)].copy()
    bn_vars_filter_2["LAYER"] = bn_vars_filter_2["LAYER"].astype(str).str.strip()
    bn_vars_filter_2.loc[bn_vars_filter_2["VARIABLE NAME"] == "DROPOUT REASON", "LAYER"] = "L9 – Dropout"
    bn_vars_filter_2 = bn_vars_filter_2.drop_duplicates(subset=["VARIABLE NAME"])
    bn_vars_filter_2.loc[bn_vars_filter_2["VARIABLE NAME"] == "DROPOUT REASON", "LAYER"] = "L9 – Dropout"
    df_clean_reduced.rename(columns=NAME_MAPPING, inplace=True)
    bn_vars_filter_2["VARIABLE NAME"] = bn_vars_filter_2["VARIABLE NAME"].replace(NAME_MAPPING)
    bn_vars_filter_2.loc[bn_vars_filter_2["VARIABLE NAME"] == "DROPOUT REASON", "LAYER"] = "L9 – Dropout"

    df_clean_reduced = translate_labels(df_clean_reduced)
    df_clean_reduced = normalise_string_categories(df_clean_reduced)
    enforce_domain_categories(df_clean_reduced)

    df_imp = impute_dataframe(df_clean_reduced, config.seed)
    enforce_domain_categories(df_imp)
    if "ATHEROSCLEROTIC CARDIOVASCULAR DISEASE HISTORY" in df_imp.columns:
        df_imp["ATHEROSCLEROTIC CARDIOVASCULAR DISEASE HISTORY"] = df_imp["ATHEROSCLEROTIC CARDIOVASCULAR DISEASE HISTORY"].astype(str)

    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    df_clean_reduced.to_parquet(output_dir / 'df.parquet', index=False)
    df_imp.to_parquet(output_dir / 'df_imp.parquet', index=False)
    bn_vars_filter_2.to_parquet(output_dir / 'bn_vars.parquet', index=False)

    baseline_table = build_baseline_table_by_group(df_clean_score)
    if not baseline_table.empty:
        baseline_csv = output_dir / "baseline_table_by_group.csv"
        baseline_parquet = output_dir / "baseline_table_by_group.parquet"
        baseline_table.to_csv(baseline_csv, index=False)
        baseline_table.to_parquet(baseline_parquet, index=False)
        LOGGER.info("Wrote baseline table (%s rows) to %s", len(baseline_table), baseline_csv)
    else:
        LOGGER.warning("Baseline table is empty; skipping export.")

    LOGGER.info("Wrote df.parquet (%s rows)", len(df_clean_reduced))
    LOGGER.info("Wrote df_imp.parquet (%s rows)", len(df_imp))
    LOGGER.info("Wrote bn_vars.parquet (%s rows)", len(bn_vars_filter_2))


def parse_args() -> PreprocessConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--risk-region", type=str, default="Low", help="Risk region for SCORE2 (Low/Moderate/High/Very high)")
    parser.add_argument("--raw-dir", type=Path, default=None, help="Override raw data directory")
    parser.add_argument("--codebook-path", type=Path, default=None, help="Path to codebook Excel")
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory to write parquet outputs")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--config", type=Path, default=None, help="Optional YAML file with path overrides")
    args = parser.parse_args()

    cfg = PreprocessConfig(
        project_root=args.project_root,
        risk_region=args.risk_region,
        raw_dir=args.raw_dir,
        codebook_path=args.codebook_path,
        output_dir=args.output_dir,
        seed=args.seed,
    )

    config_candidates = []
    if args.config is not None:
        config_candidates.append(args.config)
    default_config = cfg.project_root / "config" / "data_paths.yml"
    if default_config.exists():
        config_candidates.append(default_config)

    for cfg_path in config_candidates:
        try:
            with cfg_path.open('r', encoding='utf-8') as fh:
                overrides = yaml.safe_load(fh) or {}
        except FileNotFoundError:
            continue
        if not isinstance(overrides, dict):
            raise ValueError(f"Config file {cfg_path} must define a mapping of keys")
        LOGGER.info("Applying configuration from %s", cfg_path)
        cfg.apply_overrides(overrides)

    return cfg


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = parse_args()
    preprocess(config)


if __name__ == "__main__":
    main()
