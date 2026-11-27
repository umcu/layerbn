# Bins and sample size

## Bins

The network works on categories, so continuous variables are cut into bins, and **every
result is conditional on the bins**. Look at the bins figure and table before anything else.

| If | Then |
| --- | --- |
| A bin has very few participants | Its probabilities are unreliable, and arcs to it are harder to find. |
| A variable is binned coarsely | A relation inside a bin is invisible. Use more bins or your own `cutpoints`, at the cost of thinner data. |
| You compare cohorts | Quantile bins differ between samples. Set `cutpoints` so both use the same edges. |
| You report a bin | The readable names are rounded. The exact edges are in the column `Exact edges` of the bins table. |

```yaml
discretisation:
  method: quantile          # equal numbers per bin; or uniform: equal widths
  bins: 4
  categorical_max_levels: 10
```

A single variable can have its own `bins`, `cutpoints` or `type` in
[variables.xlsx](../guide/workbook.md).

!!! warning "Bin edges depend on the software version"

    The same data can give slightly different quantile edges with another version of pyAgrum
    or scikit-learn (36.25 or 36.275, say). Report the versions and the exact edges. layerbn
    limits the versions it accepts for this reason.

## Sample size

Each variable has a probability table that grows with its number of states and those of its
parents. With few participants the tables are poorly estimated, fewer arcs are found, and
those found are less stable.

!!! abstract "How well the example recovers its own structure"

    The example data come from a known network of 8 variables, binned into 4. Over 8
    simulated samples, layerbn found about **75% of the true arcs with 400 participants** and
    about **80% with 800**, and about 85% of the arcs it found were true. Most errors were
    arcs inside a layer drawn the wrong way round, which the data cannot settle. Your data
    will differ.

If the sample is small, reduce the number of variables, `bins` and `max_parents`.

## Missing data and loss to follow-up

Missing values are not modelled. Impute them beforehand, or analyse complete cases with
`data: missing: drop_rows`, which can bias the result; the report says how many participants
were removed.

Loss to follow-up that depends on the outcome is not modelled either. To represent it, add a
variable such as *lost to follow-up* (yes/no) in a layer after the outcome, and use
[rules](../guide/rules.md) to say what it may depend on.
