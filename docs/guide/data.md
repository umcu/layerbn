# 1 · Prepare the data

layerbn starts from an **analysis-ready table**. Deriving the outcome, choosing the follow-up,
recoding categories and imputing missing values are decisions about your cohort; you make
them in your own software (SPSS, Stata, R, Excel) before layerbn sees the data.

## What the table should look like

One row per participant, one column per variable, the column names in the first row:

| ID | AGE | SEX | SMOKING | SBP | SCORE_A | EVENT |
| --- | --- | --- | --- | --- | --- | --- |
| 1001 | 63.5 | Female | Never | 142 | 27 | No |
| 1002 | 71.2 | Male | Current | 158 | 22 | Yes |
| 1003 | 58.9 | Female | Former | 131 | 29 | No |

## Checklist

Go through this list before you copy the file into the project. Every item avoids an error
message later.

- [x] **Column names in the first row**, short and without spaces: `AGE`, `SBP`, `SCORE_A`.
      You will type them again in `variables.xlsx`, and they must match exactly, including
      capital letters.
- [x] **Only the participants you want to analyse.** Apply your inclusion and exclusion
      criteria first.
- [x] **Missing values are empty cells.** Codes such as `-99`, `999`, `.` or `NA` written as
      text are read as real values. Make them empty. Then either impute them, or let layerbn
      use only complete rows (`missing: drop_rows` in [step 4](settings.md)).
- [x] **Categories as words where you can**: `Female`/`Male`, `No`/`Yes`, `Never`/`Former`/`Current`.
      These words appear in the figures. Numeric codes (`0`/`1`) also work: a number column
      with at most 10 different values is treated as categories.
- [x] **Continuous variables as plain numbers**, without units or text: `63.5`, not
      `63.5 years`. They are cut into 4 groups of equal size by default. You can choose the
      number of groups, or your own cut-offs, per variable.
- [x] **The outcome as one column**, for example `No`/`Yes` for an event during follow-up.
      layerbn does not handle dates or time-to-event: derive the outcome yourself.
- [x] **No variables that are almost the same.** Two versions of one measurement (raw and
      standardised, say) compete for the same arcs. Keep one.
- [x] **Extra columns are fine.** An ID column or variables you do not list are ignored, and
      the run notes which columns it did not use.

!!! warning "Loss to follow-up"

    Participants without an outcome are either missing (and dropped with `drop_rows`), or you
    code the reason as a category of its own, for example `No` / `Yes` / `Lost to follow-up`.
    The second keeps everyone and lets the network show what is related to dropping out.

## How many participants and variables?

Each variable gets a probability table with one cell for every combination of its own groups
and those of its parents. More variables, groups and parents need more participants.

!!! abstract "A practical guide"

    **A few hundred participants for 15 to 20 variables** with 4 groups each. With fewer
    participants, use fewer variables, fewer groups (`bins: 3`) and fewer parents
    (`max_parents: 3`), and expect lower arc stability. Start small: a first network with 10
    well-chosen variables teaches you more than one with 40.

## Save the table and put it in the project

Save the table in one of these formats and copy it into the `data` folder of your project.

=== "Excel"

    Keep it as `.xlsx`. The data must be on the **first sheet**, with the column names in row 1
    and nothing above them (no titles, no merged cells).

    Or *File → Save As → CSV*. A CSV saved with semicolons and decimal commas, as Excel does
    with Dutch or German settings, is recognised.

=== "SPSS"

    Save as `.sav` and use that file directly; value labels become the category names. This
    needs one extra package: `python -m pip install pyreadstat`.

    Or *File → Export → CSV Data*, with *Save value labels where defined* selected.

=== "Stata"

    `save "my_cohort.dta"`, and use the `.dta` file directly. Value labels become the category
    names.

=== "R"

    ```r
    write.csv(cohort, "my_cohort.csv", row.names = FALSE, na = "")
    ```

    `na = ""` writes missing values as empty cells. Convert factors you want to see by name
    with `as.character()` first if they are stored as numbers.

=== "Python"

    ```python
    cohort.to_csv("my_cohort.csv", index=False)
    ```

Then, in the terminal, check that the file is where layerbn will look:

```bash
ls data          # Windows: dir data
```

You should see your file, for example `my_cohort.csv`. You will write this name in
`settings.yml` in [step 4](settings.md).

??? info "Variables measured at several time points"

    Give each variable and time point its own column, with the time point as a suffix:
    `SCORE_T0`, `SCORE_T1`. See [Measurements over time](repeated.md). Variables measured
    once need no suffix.

[Next: order the variables :material-arrow-right:](layers.md){ .md-button .md-button--primary }
