# 3 · Fill in variables.xlsx

Open `variables.xlsx` from your project folder in Excel. Delete the example rows, keeping the
header row, or start from empty tables with `layerbn init my-study --blank`. The sheet
`instructions` inside the workbook repeats what follows.

The workbook has three sheets. Most studies only need the first two.

=== "layers"

    One row per layer, **in causal order**: rows higher up come first.

    | layer | label | repeated | arcs_within | colour |
    | --- | --- | --- | --- | --- |
    | Background | | no | | |
    | Exposures | | no | | |
    | Baseline measures | | no | | |
    | Outcome | | no | no | |

    | Column | Fill in |
    | --- | --- |
    | `layer` | A short name. You pick it from a dropdown on the `variables` sheet. |
    | `label` | Optional. The name shown in figures, if it differs. |
    | `repeated` | `no`, unless the same variables were measured at several time points. See [Measurements over time](repeated.md). |
    | `arcs_within` | `no` to forbid arcs between variables of this layer. Empty: allowed. |
    | `colour` | Optional. A name such as `steelblue` or a code such as `#2166ac`. |

=== "variables"

    One row per variable.

    | variable | label | layer | type | bins | cutpoints | target |
    | --- | --- | --- | --- | --- | --- | --- |
    | AGE | Age (years) | Background | | | | |
    | SEX | Sex | Background | categorical | | | |
    | EXPOSURE_A | Exposure A (score) | Exposures | | | | |
    | OUTCOME | Outcome at follow-up | Outcome | categorical | | | yes |

    | Column | Fill in |
    | --- | --- |
    | `variable` | The column name in your data file, exactly. |
    | `label` | Optional. The name shown in figures and tables. |
    | `layer` | Pick from the list. |
    | `type` | Empty: decided from the data. `categorical`: keep a numeric variable as categories (a group coded 1, 2, 3). `continuous`: bin a numeric variable with few values. |
    | `bins` | Optional. A number of bins other than the default. |
    | `cutpoints` | Optional. Your own thresholds, such as `24; 27` for below 24, 24 to 27, and 27 or higher. Use it for established cut-offs in your field. |
    | `target` | `yes` for the variables you are mainly interested in, usually the outcome. |

=== "timepoints"

    **Leave empty** unless a layer is marked `repeated`. See
    [Measurements over time](repeated.md).

!!! tip "Use the dropdowns"

    Layer names, yes/no fields and types are dropdown lists, so the most common mistake, a
    layer spelt differently in two places, cannot happen. Columns named `note` or `comment` are
    yours: layerbn ignores them.

Prefer plain text? The same tables can be CSV files (`variables.csv`, `layers.csv`) in the
project folder. See the [reference](../reference/variables.md).

[Next: choose the settings :material-arrow-right:](settings.md){ .md-button .md-button--primary }
