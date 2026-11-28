# variables.xlsx

An Excel workbook with the sheets `variables`, `layers` and `timepoints`, in any order. A
sheet named `instructions` is ignored. As an alternative, the same tables can be CSV files
named `variables.csv`, `layers.csv` and `timepoints.csv` in one folder (comma, semicolon or
tab separated). Column headers are not case sensitive and spaces count as underscores. A
column whose header starts with `note` or `comment` is ignored. Any other unknown header is an
error, with a suggestion, so a misspelt header is never silently ignored.

## Sheet `layers`

Optional if no layer is repeated and you accept the default order: then the layers are the
layer names on the `variables` sheet, in order of first appearance. **When the sheet is
present, the order of its rows is the causal order.**

| Column | Values | Meaning |
| --- | --- | --- |
| `layer` | text, required | Name of the layer. Must be unique. |
| `label` | text | Name shown in figures. Default: `layer`. |
| `repeated` | `yes` / `no` | Only for variables measured more than once: the layer is expanded into one layer per time point. Default: `no`. |
| `arcs_within` | `yes` / `no` | Whether arcs between variables of this layer are allowed. Default: the setting `constraints: within_layers` (`yes`). |
| `colour` | colour name or hex code | Colour of the layer in figures. Default: the standard sequence of colours. |

Every layer needs at least one variable. Layers marked `repeated` must follow each other
directly, and at least one time point must be defined.

## Sheet `variables`

| Column | Values | Meaning |
| --- | --- | --- |
| `variable` | text, required | Column name in the data. For a repeated layer, the name without the time point. Must be unique. |
| `label` | text | Name shown in figures and tables. For a repeated layer the time point label is appended: `Score, Second visit`. Default: `variable`. |
| `layer` | text, required | A layer from the `layers` sheet. |
| `type` | `categorical` / `continuous` / empty | Empty: numeric columns with more than `categorical_max_levels` distinct values are binned, everything else is used as categories. `categorical`: never binned. `continuous`: always binned, even with few distinct values. |
| `bins` | whole number, at least 2 | Number of bins for this variable. Default: `discretisation: bins`. |
| `cutpoints` | numbers separated by `;` | Thresholds that define the bins. `24; 27` gives three bins: below 24, 24 up to below 27, and 27 or higher. A comma is read as a decimal mark. Cannot be combined with `bins` or with `type: categorical`. |
| `times` | time keys separated by `;` | Repeated layers only: the time points at which the variable was measured. Default: all. |
| `target` | `yes` / `no` | A variable of main interest. See [targets](#targets). |

## Sheet `timepoints`

Only needed when a layer is repeated; otherwise leave it empty or leave it out.

| Column | Values | Meaning |
| --- | --- | --- |
| `time` | text, required | The text that appears in the data column names (`T0`). Unique. |
| `label` | text | Shown to readers (`First visit`). Default: `time`. Unique. |

The rows are in time order.

## How repeated layers are expanded

For each time point `t` in order, each repeated layer `L` is turned into a layer named
`L (label of t)`. The data column of a variable `V` is built from the column pattern
(`data: column_pattern:`, default `{variable}_{time}`), so `V` at time `T1` is `V_T1`. The
block of repeated layers sits at the position of the first repeated layer, in time-major
order: with layers `A`, `C` (repeated), `D` (repeated), `E` and time points `T0`, `T1`, the
order is `A`, `C (T0)`, `D (T0)`, `C (T1)`, `D (T1)`, `E`. A layer with no variable at some time
point (because of `times`) is left out for that time point.

## Names in settings.yml

Wherever a variable is named in `settings.yml`, either the column name (`EXPOSURE_A`) or the
label (`Exposure A (score)`) works. Wherever a layer is named, its name from the `layers`
sheet works. For a repeated layer, the name of an expanded layer (`Scores (Second visit)`)
refers to that time point only, and the name from the `layers` sheet (`Scores`) refers to it
at every time point.

## Targets

Targets are the variables you are mainly interested in. They are the default for
`importance`, `profiles` and `sweep`, and they get a solid title strip in the figures. If no variable
is marked, the variables of the last layer of the network are used.
