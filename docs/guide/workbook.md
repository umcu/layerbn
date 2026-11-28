# 3 · Fill in variables.xlsx

`variables.xlsx` tells layerbn **which columns of your data to use** and **in which layer**
each one goes. Open it from your project folder in Excel (or LibreOffice). It has four sheets:

| Sheet | You |
| --- | --- |
| `instructions` | read it once; it repeats this page |
| `layers` | fill in: one row per layer |
| `variables` | fill in: one row per variable |
| `timepoints` | leave empty, unless a variable was measured at several visits |

Fill in **`layers` first**, because the `layer` column on the `variables` sheet is a dropdown
list made from it.

## Step A · The `layers` sheet

One row per layer, **in causal order: the top row is the first layer**. Only the first column
is required.

| layer | label | repeated | arcs_within | colour |
| --- | --- | --- | --- | --- |
| Background | | no | | |
| Lifestyle | | no | | |
| Clinical | | no | | |
| Outcome | | no | no | |

| Column | Fill in |
| --- | --- |
| `layer` | **Required.** A short name. It appears in the figures. |
| `label` | Optional. A longer name for the figures, if the short one is not clear enough. |
| `repeated` | `no`, unless the same variables were measured at several time points ([how that works](repeated.md)). |
| `arcs_within` | Empty: arcs between variables of this layer are allowed. `no`: they are not. Use `no` for the outcome layer if you have several outcomes that should not be shown as causing each other. |
| `colour` | Optional. Empty uses blue for the first layer to red for the last. |

## Step B · The `variables` sheet

One row for each data column you want in the network. The order of the rows within a layer
is the order in the figures.

| variable | label | layer | type | bins | cutpoints | target |
| --- | --- | --- | --- | --- | --- | --- |
| AGE | Age (years) | Background | | | | |
| SEX | Sex | Background | | | | |
| SMOKING | Smoking | Lifestyle | | | | |
| SBP | Systolic blood pressure | Clinical | | | 120; 140 | |
| SCORE_A | Score A | Clinical | | 3 | | |
| EVENT | Event during follow-up | Outcome | | | | yes |

| Column | Fill in |
| --- | --- |
| `variable` | **Required.** The column name in your data, **exactly**, including capitals. Copy it from the header of your data rather than retyping. |
| `label` | Recommended. The name readers see in figures and tables: `Systolic blood pressure`, not `SBP`. |
| `layer` | **Required.** Choose from the dropdown list. |
| `type` | Usually empty: layerbn decides from the data. Write `categorical` to keep a number column as categories (a group coded 1 to 12), or `continuous` to cut a number column with few values into groups. |
| `bins` | Optional. The number of groups for this continuous variable, if not the default 4. |
| `cutpoints` | Optional. Your own thresholds, separated by semicolons. `120; 140` gives three groups: below 120, 120 to below 140, and 140 or higher. Use it for established cut-offs in your field. |
| `target` | `yes` for the variables you are mainly interested in, usually the outcome. They get a solid title in the figures and are the default for the analyses. |

!!! tip "Use the dropdowns"

    The `layer`, `type` and `target` columns are dropdown lists. Choosing from them prevents the
    most common mistake: a layer name typed slightly differently in two places.

!!! note "Notes for yourself"

    Columns named `note` or `comment` are ignored. Use them to record why a variable is in its
    layer: you will want that when you write the methods.

## Step C · Save and close

Save the workbook as `.xlsx` with the same name, and **close it in Excel** before you run
layerbn. On Windows, a file that is open in Excel cannot always be read.

??? question "I prefer plain text files"

    The same tables can be CSV files in the project folder, `variables.csv` and `layers.csv`,
    with the same column names. See the [reference](../reference/variables.md).

??? question "Can I see a filled-in example?"

    Yes: open `variables.xlsx` in the example project from [your first run](../start/first-run.md)
    (`layerbn init my-study`).

[Next: choose the settings :material-arrow-right:](settings.md){ .md-button .md-button--primary }
