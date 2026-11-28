# Error messages

Messages you may meet, what they mean and what to do, grouped by where they appear. Use the
search box (top right) to find a message by its words.

!!! tip "First, run a check"

    ```bash
    layerbn check my-study
    ```

    It reads the files and the data without fitting a model, and names the problem. If a
    message gives no hint, `layerbn --traceback check my-study` shows the full Python error:
    send that with a bug report.

## variables.xlsx

### `unknown column 'lable'. ... Did you mean 'label'?`

A column header is misspelt. Headers are not case sensitive, but they must be spelt as in the
[reference](../reference/variables.md). A column that is only for your own remarks should
be called `note` or `comment`, which are ignored.

### `variable 'X' is in layer 'Exposure', which is not on the 'layers' sheet. Did you mean 'Exposures'?`

The layer name on the `variables` sheet differs from the name on the `layers` sheet, here by
one letter. Use the dropdown list in the `layer` column, which only offers names from the
`layers` sheet. In a hand-edited file, copy the name instead of retyping it.

### `variable 'X' is listed twice (first on row 2)`

Each variable has one row and one layer. For a repeated layer, list the variable once without
the time point.

### `the layer(s) ['Scores'] are marked as repeated, but there is no 'timepoints' sheet`

A layer marked `repeated` is expanded over time points, which are listed on the sheet
`timepoints`. Add that sheet, with the columns `time` and `label`, or set `repeated` to `no`.

### `repeated layers must follow each other without a layer in between`

Repeated layers are expanded together into one block per time point, so they must be adjacent
on the `layers` sheet. If a layer that is measured once belongs between two repeated layers,
the order inside a time point is not what you meant. Move the layer, or consider whether it
should be repeated.

### `'T9' is not on the 'timepoints' sheet`

The `times` column of a variable names a time point that is not listed. Use the text in the
`time` column of the `timepoints` sheet, separated by semicolons.

### `variable 'X' has 'times' set, but its layer 'Y' is not repeated`

`times` is for variables in repeated layers only. Empty the cell, or mark the layer as
repeated.

### `give either 'bins' or 'cutpoints', not both` and `a categorical variable is not binned`

A variable is binned in one way only. `cutpoints` fixes the thresholds, `bins` only the number
of bins, and a categorical variable is not binned at all.

### `'x' is not a colour`

Use a colour name such as `steelblue` or a hex code such as `#2166ac` in the `colour` column.

### `the label 'X' appears more than once after the time points are expanded`

Two variables have the same label. Labels, columns and layer names must be unique. For a
repeated layer, the time point label is appended automatically.

### `'X' is the column of one variable and the label of another`

A name must identify one variable. Change the label.

### `layer 'X' has no variables`

A layer on the `layers` sheet has no row on the `variables` sheet. Remove it from the `layers`
sheet or add its variables. Often this is a layer name that differs slightly.

### `no variables found`

The `variables` sheet has no rows. You may have started from `layerbn init --blank` and not
filled it in yet.

## settings.yml

### `bootstrap.resample: unknown setting. ... Did you mean 'resamples'?`

An unknown setting is an error, so that a misspelt setting is not silently ignored. The
message lists the allowed settings for that block.

### `learning.score: 'K3' is not allowed. Choose one of ['K2', 'BIC', 'BDeu']`

A value is not one of the allowed ones. The message lists them.

### `this is a version 2 spec ... layerbn migrate spec.yml`

The file is in the format of version 2. Convert it with `layerbn migrate spec.yml`. See the
[upgrade guide](../about/upgrading.md).

### `the file is not valid YAML`

A syntax error in the file. Common causes: a tab instead of spaces (YAML allows only spaces
for indentation), a colon in a text value that is not in quotation marks, an unmatched bracket
or quotation mark. Indentation carries meaning: lines inside a block start with the same number
of spaces.

### A category named `Yes` or `No` in a profile

YAML reads an unquoted `yes`, `no`, `true`, `false`, `on` and `off` as true or false. layerbn
matches such a value to a category called `Yes`, `No`, `Ja`, `Nee`, `True`, `False`, `1` or `0`
in the data, so `OUTCOME: No` works. For any other category that looks like one of these
words, put it in quotation marks: `GROUP: "off"`.

## Settings and variables together

### `constraints.forbid[0].from: 'AGEE' is not a variable in the design. Did you mean 'AGE'?`

A variable or layer named in the settings does not exist in the variables table. Names can be
column names or labels. Layers can be the name from the `layers` sheet (all time points) or
for a repeated layer, the expanded name such as `Scores (Second visit)`.

### `... runs against the layer order`

You required an arc from a later layer to an earlier layer. Rules can only narrow what the
layer order allows; they cannot allow an arc against it. The layer order is your statement of
what can influence what. If the arc should be possible, move a variable or change the order of
the layers.

### `... is both required and forbidden`

Two rules contradict each other. A rule that names a layer covers all the variables in it, so
a broad `forbid` can collide with a narrower `require`. Remove one, or name specific variables.

### `... is inside layer 'X', which has arcs_within set to no`

You required an arc between two variables of a layer in which arcs are not allowed. Change
`arcs_within` for that layer, or the rule.

### `... must have the parent X but is also listed under no_parents`

A variable is both required to have a parent and not allowed to have one. Remove it from one
of the two.

### `network 'x' has 1 variable(s) after the exclusions. A network needs at least two.`

The exclusions in `networks:` leave too little. Check `exclude_layers` and `exclude_variables`.

### `there is no network named 'x'. The networks are [...]`

A network named in `analyses:` or on the command line (`--network`) is not in `networks:`.

### `the variable that is moved across its states cannot also be held fixed`

In `analyses: sweep:`, remove the variable from `fixed:`.

## The data

### `N variable(s) in the design table are not columns of the data file`

The message lists them, with a suggestion where a similar column exists. Column names must
match exactly. The usual causes, most common first:

* Capital letters or spaces differ (`Age` and `AGE`).
* For repeated measures, the data column does not follow the pattern. With the default
  pattern, `SCORE` at time point `T1` is looked up as `SCORE_T1`. Check the `time` column
  of the `timepoints` sheet, and `data: column_pattern:`.
* The variable is not in this data file.

### `The data has missing values in N variable(s)`

The network is learned from complete data. Impute the values before the analysis, or set
`data: missing: drop_rows` to analyse the participants with complete data. The second option
can bias the results. The report states how many participants were removed.

### `These variables have only one value in the data`

A variable that does not vary has no information. Remove it from the variables table.

### `type is 'continuous' but the column is not numeric`

The column holds text, for example numbers with units or a decimal comma stored as text.
Convert it to a number before the analysis, or set `type` to `categorical`.

### `data file not found`

A relative path in `data: file:` is taken relative to the folder of `settings.yml`, not to
where you opened the terminal. Give a full path, or use `--data`.

### `cannot read '.xyz' files`

Supported: `.csv`, `.tsv`, `.xlsx`, `.xls`, `.parquet`, `.feather`, `.sav`, `.dta`.
Parquet needs `pip install pyarrow` and SPSS `pip install pyreadstat`.

### A column of numbers is read as categories (or the reverse)

A numeric column with at most `categorical_max_levels` (default 10) different values is not
binned. Set `type` to `continuous` to bin it, or `categorical` to keep a column with many
values as categories (a diagnosis coded 1 to 15). Read the bins table to see how each variable
was treated.

## Notes during a run

These are printed during the run and listed in the report. They are not errors.

### `N column(s) of the data file are not in the design table and are not used`

The data has columns that you did not list, such as an identifier. They are left out. If a
real variable is among them, add it to the variables table.

### `N of M bootstrap fits failed`

A resample could not be fitted. A few out of a few hundred are not a concern. Frequencies are
divided by the number of resamples you asked for, so failures lower them slightly instead of
being left out. If many fail, the data are too thin for the settings: use fewer bins
(`discretisation: bins`), fewer parents (`learning: max_parents`), or remove a layer.

### `group: placed in bins: AGE: 65 -> 63.4 to < 69`

Not a problem. It shows the bin that the value fell in. If you meant a narrower group, the
bins are wider than you assumed. Set `cutpoints` for the variable.

### `group: NOT USED: SEX='F' (no such state; states are ['Female', 'Male'])`

A value of a profile could not be placed, so that variable is not part of the profile. The
message lists the states that exist. The variable may also be missing from this network
(`not in network`), for example because its layer is excluded.

### `No value of the profile(s) [...] could be used`

None of the values of a profile could be placed, so there is nothing to condition on.

### `sweep: [...] lie downstream of X in the learned network`

A variable held fixed in the sweep lies between the moved variable and the targets, which
blocks part of the effect. The curves can be flat for that reason. Fix only variables that
come before the moved variable in the layer order.

### `The profile analysis was skipped` / `The sweep was skipped`

The rest of the run continues, and the reason is given. Fix the settings and run again.

## The results

### An arc I expected is missing

In this order:

1. Does the layer order allow it? An arc from a later to an earlier layer never occurs.
2. Do `forbid` rules or `arcs_within: no` rule it out?
3. Is it in the table of arc stability (`tables/arcs_<network>.csv`) with a moderate
   frequency? An arc in 40% of the resamples need not be in the single network.
4. Are both variables binned finely enough to show the relation (the bins figure)? Is the
   sample large enough for the number of parents and bins?
5. Is a correlated variable taking its place? Look for an arc from the other variable into
   the same child.

### `In network` and a high frequency disagree

They answer different questions. One is the arc in the network learned from all the data, the
other is how often it appears under resampling. Report the frequency.

### The network is almost empty

The sample is small for the number of variables and bins, or the `max_parents` is low, or the
score is BIC, which gives sparser networks. Try fewer bins and variables, or K2.

### The sweep is flat

Check, in order: a variable between the moved variable and the target is held fixed (a note
says so); the variable does not carry information about the target in this model, which is a
result; the bins of the variable are too coarse (the bins figure).

### Mutual information of a variable is `NaN`

The computation failed for that variable. It is shown as missing instead of being left out of
the table, so that a gap is visible. Send the bug report with `--traceback`.

### Figures differ between computers

Figures use Arial where it is installed and DejaVu Sans otherwise. The numbers do not depend on
the font.

## Installation and speed

### `layerbn: command not found`

Use `python -m layerbn` instead of `layerbn`. Or the folder where pip puts commands is not on
your PATH; the `python -m` form avoids that.

### `ModuleNotFoundError: No module named 'pyarrow'` (or `openpyxl`, `pyreadstat`)

Install the package: `pip install pyarrow`. `openpyxl` is installed with layerbn. `pyarrow` is
needed for Parquet files and `pyreadstat` for SPSS files.

### `PermissionError` when reading or writing a file

On Windows, a file that is open in Excel cannot be written, and sometimes not read. Close
`variables.xlsx` and `tables.xlsx` (in `results/tables/`) and run again.

### The run takes too long

The time is dominated by the number of bootstrap resamples, and is roughly proportional to it.
Use `--fast` or set `bootstrap: resamples: 20` while you set up, and the full number only for
the run you report. `learning: search: greedy` is faster and searches less thoroughly. Fewer
variables, bins and parents also help. The run prints an estimate of the time left.

### Warnings about `swigvarlink` or scikit-learn `quantile_method`

Notices from libraries that layerbn uses. They do not affect the results. The version of
scikit-learn is limited to below 1.9 because that release changes how quantile bin edges are
computed, which would change every result. The test suite checks the bin edges for this
reason.
