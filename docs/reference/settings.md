# settings.yml

All settings are optional except those you want to differ from the defaults. An unknown
setting is an error with a suggestion. The file created by `layerbn init` explains each
setting in comments.

The whole file, with every setting and its default or an example:

```yaml
settings_version: 3
name: text                      # shown in the report
description: text               # shown in the report
output_dir: results             # relative to this file, or a full path

data:
  file: data/cohort.csv         # relative to this file, or a full path
  variables_file: variables.xlsx   # default: variables.xlsx or variables.csv beside this file
  missing: error                # error | drop_rows
  column_pattern: "{variable}_{time}"

discretisation:
  method: quantile              # quantile | uniform
  bins: 4                       # at least 2
  categorical_max_levels: 10    # numeric variables with at most this many values are not binned

learning:
  score: K2                     # K2 | BIC | BDeu
  search: tabu                  # tabu | greedy
  max_parents: 5
  seed: 42

bootstrap:
  resamples: 200

constraints:
  within_layers: true           # default for layers without their own arcs_within
  forbid:   [ {from: A, to: B}, {from_layer: X, to_layer: Y} ]
  require:  [ {from: C, to: D} ]
  no_parents:  [A]
  no_children: [B]

networks:
  - name: all_variables
    description: text
    exclude_layers: [Layer name]
    exclude_variables: [VARIABLE]
    resamples: 50               # overrides bootstrap: resamples

analyses:
  importance:
    targets: [VARIABLE]
  profiles:
    network: all_variables
    resamples: 200
    targets: [VARIABLE]
    groups:
      "Group name": {VARIABLE: value, OTHER: value}
  sweep:
    network: all_variables
    resamples: 200
    variable: VARIABLE
    fixed: {OTHER: value}
    targets: [VARIABLE]
```

## data

| Setting | Meaning |
| --- | --- |
| `file` | The data file. Can instead be given with `--data` on the command line. |
| `missing` | `error`: stop and list variables with missing values. `drop_rows`: analyse participants with complete data and report how many were removed. |
| `column_pattern` | Only for repeated layers: how the data columns of a variable at each time point are named. May use `{variable}` and `{time}`. Default `{variable}_{time}`. |

## discretisation

Continuous variables are cut into bins. `quantile` gives bins with about equal numbers of
participants. `uniform` gives bins of equal width. A numeric variable with at most
`categorical_max_levels` distinct values is used as categories. Per-variable settings in the
`variables` sheet take precedence.

## learning

| Setting | Meaning |
| --- | --- |
| `score` | The score that structure learning maximises. K2 and BDeu are Bayesian scores with their own prior. BIC penalises complexity more and gives sparser networks; a smoothing prior is added for BIC only, so that a combination of parent states that does not occur in a resample gets a small probability instead of zero. |
| `search` | `tabu` searches more thoroughly than `greedy` hill climbing and is slower. |
| `max_parents` | The most parents any variable may have. Each extra parent multiplies the size of the probability table of the variable. |
| `seed` | Makes a run reproducible. Resample `i` uses the seed `seed + i`. |

## bootstrap

The number of resamples. Each resample draws participants with replacement, learns the
structure and parameters again, using the bins of the full data, and records the arcs.
Run time is roughly proportional to this number.

## constraints

Rules narrow what the layer order permits. They cannot permit an arc that runs against it,
and requiring such an arc is an error that says so.

| Setting | Meaning |
| --- | --- |
| `within_layers` | Whether arcs between variables of one layer are allowed. A layer can differ through its own `arcs_within`. |
| `forbid` | Arcs that must not occur. Each end is a variable (`from`, `to`) or a whole layer (`from_layer`, `to_layer`); the two can be mixed. A layer stands for all its variables. |
| `require` | Arcs that must occur. Checked against the layer order, the other rules and each other. A rule that names a variable not present in a network is ignored for that network. |
| `no_parents` | Variables that may have no parents (roots). |
| `no_children` | Variables that may have no children (sinks). |

## networks

Each entry is a network learned and bootstrapped separately. Without this block, one network
named `main` with all variables is learned. `exclude_layers` and `exclude_variables` remove
variables from that network. Layers keep their order. A network needs at least two variables.

## analyses

| Analysis | Runs on | Meaning |
| --- | --- | --- |
| `importance` | every network | Mutual information of each variable with each target, and its relation to the target in the learned network. |
| `profiles` | one network (`network:`, default the first) | Probability of each state of the targets for each named group, with a bootstrap interval. |
| `sweep` | one network (`network:`, default the first) | Probability of the targets as `variable` moves across its states while `fixed` is held. |

Values in `groups` and `fixed` can be a number (placed in the bin that contains it), a
category name, or a bin as written in the bins table (`"≥ 27"`). A value that cannot be placed
is reported and left out of that profile.
