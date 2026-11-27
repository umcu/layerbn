# 1 · Prepare the data

layerbn starts from an **analysis-ready table**. Deriving outcomes, handling censoring,
harmonising categories and imputing are decisions about your cohort, and you make them before
layerbn sees the data.

## The shape

One row per participant, one column per variable, with a header row.

| AGE | SEX | EXPOSURE_A | EXPOSURE_B | MEASURE_1 | … | OUTCOME |
| --- | --- | --- | --- | --- | --- | --- |
| 63.2 | Female | 41.0 | No | 49.7 | … | No |
| 71.5 | Male | 58.3 | Yes | 38.1 | … | Yes |

The column names are how layerbn finds each variable, so they must match `variables.xlsx`
exactly, including capital letters and spaces. Other columns, such as an identifier, are
allowed and ignored.

**File formats:** CSV, Excel (`.xlsx`), Stata (`.dta`), SPSS (`.sav`, needs `pyreadstat`),
Parquet and Feather (need `pyarrow`). CSV files separated by semicolons, as Excel writes them
in many countries, are read too.

## Checklist

- [x] **No missing values.** The network is learned from complete data. Impute before the
      analysis, or set `data: missing: drop_rows` to analyse complete cases. That can bias
      the results if values are not missing at random, and the report says how many
      participants were removed.
- [x] **Categories as you want them in the figures.** A text column (`Female`, `Male`) is used
      as categories. So is a numeric column with at most 10 different values, such as a 0 to 5
      rating. A numeric column with more values is cut into bins. You can override this per
      variable in [step 3](workbook.md).
- [x] **Enough participants.** See below.

## How many participants?

Each variable gets a probability table with one cell for every combination of its own states
and those of its parents. More variables, bins and parents need more data.

!!! abstract "A practical guide"

    A few hundred participants for 15 to 20 variables with 4 bins. With fewer participants,
    use fewer bins (`bins: 3`), fewer parents (`max_parents: 3`) and fewer variables, and
    expect lower arc stability. The bootstrap will show it: arcs that rest on a handful of
    participants appear in few resamples.

??? info "Variables measured at several time points"

    Give each variable and time point its own column, with the time point as a suffix:
    `SCORE_T0`, `SCORE_T1`. See [Measurements over time](repeated.md). Variables measured
    once need no suffix.

[Next: order the variables :material-arrow-right:](layers.md){ .md-button .md-button--primary }
