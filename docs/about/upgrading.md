# Upgrading from version 2

Version 3 describes an analysis in two files instead of three, and no layer has a special
meaning any more. Convert an existing version 2 analysis with one command:

```bash
layerbn migrate spec.yml
```

It writes `settings.yml` and `variables.xlsx` to a new folder `migrated` (or `--out FOLDER`).
Check the result with `layerbn check migrated --figure` before running it.

## What changes

| Version 2 | Version 3 |
| --- | --- |
| `spec.yml` + `config.yml` | `settings.yml` + `variables.xlsx` |
| Layer roles `outcome` and `selection` | Gone. Mark variables of interest as `target`; use `arcs_within: no` and rules where needed. |
| Arcs from outcomes into dropout, added after learning | Written as `require` and `forbid` rules by `migrate`, and learned with the rest. |
| `variants`, `n_bins`, `max_indegree`, ... | `networks`, `bins`, `max_parents`, ... |
| Conditional mutual information | Removed; the relation to the target is given instead. |
| Graphviz figures | matplotlib figures, no Graphviz needed. |

!!! warning "Results can change"

    A required arc is now part of the learning, and pyAgrum and the bins can differ from the
    versions you used. Do not expect identical numbers when you re-run an analysis you have
    already reported. Read the [changelog](changelog.md) first.
