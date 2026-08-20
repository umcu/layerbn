# Troubleshooting

Messages you are likely to meet, what each one means, and what to do. They are
grouped by when they appear.

If a message is not here, the first thing to try is `python -m layerbn check spec.yml`,
which validates the spec on its own and usually names the problem.

---

## Loading the spec

### `SpecError: spec.yml: variants[0].exclude_layers[0]: 'L2 - Optional markers' is not a declared layer. Did you mean 'L2 – Optional markers'?`

Two different dash characters. `-` is a hyphen; `–` is an en dash. They look
nearly identical and are not the same string.

Copy the layer name from the `layers:` block rather than retyping it. This is
the single most common spec error, which is why the loader suggests the close
match.

### `SpecError: spec.yml: layers[3].variables[1]: variable 'AGE' already appears in layers[0] ('L0 – Demographics'). A variable must belong to exactly one layer.`

Each variable sits in exactly one layer, because its layer is what determines
which arcs it may take part in. Decide where it belongs and remove the other
entry.

### `SpecError: spec.yml: layers[].role: no layer declares 'role: outcome'.`

At least one layer must be marked as holding the outcomes. Without it the
learner cannot tell endpoints from covariates, and cannot forbid arcs between
outcomes.

### `SpecError: spec.yml: analyses.knob_sweep.base_profile.MEASUREMENT A: the knob 'MEASUREMENT A' must not also be fixed in base_profile`

The sweep varies the knob across all of its states, so fixing it at one value
would contradict the whole point. Remove it from `base_profile`.

### `SpecError: constraints.require[0]: ... is in the earlier layer 0. Constraints may only narrow what the layer order allows.`

You required an arc that runs upstream. Constraints can only restrict what the
layer order already permits, never extend it, so that the `layers` list stays
a complete statement of what the learner may do.

If the arc should be possible, the layer order is what to change. If two
variables genuinely influence each other in both directions, no acyclic
network can represent that, and the usual fix is to put them in the same layer
and let `within_layers` allow a single arc in whichever direction the data
support.

### `SpecError: constraints.require[0]: 'A' -> 'B' is both required and forbidden.`

Two rules contradict each other. Remember that a rule naming a layer expands
to every variable in it, so a broad `forbid` on a layer pair can easily catch
an arc a narrower `require` asked for. Remove it from one of the two lists, or
narrow the layer rule to specific variables.

### `SpecError: constraints.require[0]: ... requires an arc between the outcomes ... but constraints.arcs_between_outcomes is false.`

By default no endpoint may be a cause of another endpoint. If you genuinely
intend one outcome to predict another, set `arcs_between_outcomes: true`. Think
about whether the second outcome then belongs in a later layer instead.

### `SpecError: constraints.require[0]: ... is in the selection layer and constraints.selection_parents is 'outcomes'.`

Only outcomes may point into the dropout layer under the default. Set
`selection_parents: any` if participants in your cohort leave for reasons
unrelated to the endpoints, such as moving away, and you want covariates to be
able to explain dropout.

### `SpecError: spec_version: ... constraints was added in spec version 2, but this file declares version 1.`

Set `spec_version: 2`.

### `SpecError: spec_version: this file uses constraints but does not declare a version.`

Add `spec_version: 2` at the top. Leaving it out is not the same as declaring
it: a loader older than version 2 assumes version 1, so an undeclared file
would be accepted, its constraints ignored, and an unconstrained network
learned without anything being reported. The declaration is what makes an old
loader refuse the file instead.

### `ValueError: these arcs are both mandatory and forbidden: [...]`

The same contradiction as above, but raised from `build_bn` rather than the
spec loader, which means the constraints were passed directly in code. Loading
them from a spec catches this earlier and names the offending key.

### `SpecError: spec file not found: spec.yml`

The path is relative to the directory the notebook or the shell is running in,
not to where the spec lives. Either `cd` to the project folder first, or give
`SPEC_PATH` an absolute path.

---

## Loading the data

### `FileNotFoundError: data file not found: .../analysis_ready.parquet`

`data.path` in the spec points at something that is not there. It is a file
name, looked up inside `data_dir` from `config.yml`. Check that `data_dir` is
the folder you meant:

```bash
python -c "from layerbn.config import load_project_config as l; print(l('config.yml'))"
```

While setting up, `USE_DEMO_DATA = True` skips this entirely.

### `MISSING from the data (3): ['MARKER 1', 'MARKER 2', 'RISK SCORE']`

The spec declares variables that are not columns in your table. They cannot be
modelled. Either the names disagree, often by whitespace or capitalisation, or
the preprocessing did not produce those columns.

Compare against `df.columns` — an exact string match is required.

### `Not in any layer, set aside (2): ['PATIENT ID', 'SITE']`

Your table has columns the spec does not mention. They are excluded, so the
network contains exactly what the spec declares. This is normal for
identifiers. If a real variable appears here, add it to a layer.

---

## Discretisation

### An ordinal score has been cut into bins

Anything numeric with more than `discretisation.threshold` distinct values gets
binned. A 0–20 scale therefore gets binned by default. Raise `threshold` above
the number of distinct values to keep it as it is.

### The bins are too coarse to show anything

Raise `discretisation.n_bins`. The cost is real: each variable's conditional
probability table grows with the number of states of the variable and of every
parent, so more bins means fewer participants per cell and less power to detect
an arc at all. Four is a reasonable default.

Check `study.bins(...)` after any change.

---

## Structure learning

### `[aGrUM notification] The K2 score already contains a different 'implicit' prior. Therefore, the learning will probably be biased.`

**This should no longer appear.** Up to v1.2.1 the knob sweep forced a Laplace
smoothing prior on top of whichever score you chose, and K2 — the default —
carries an implicit prior already. pyAgrum was reporting a real problem: the
two priors were being counted together, and the sweep's resamples were
therefore learned under different assumptions from the network being reported.

Since v2.0.0 the smoothing prior is applied only for BIC, the one supported
score without a prior of its own, so the message does not arise.

If you see it, something is passing `use_smoothing=True` to `build_bn`
directly. Remove it; it is ignored for K2 and BDeu by design.

### `Bootstrap 17 failed: ...` and `Note: 3/200 bootstrap fits failed`

A resample happened to contain no participants in some combination of states,
so that fit could not complete. A handful out of a few hundred is not a
concern.

Frequencies are divided by the number of resamples requested, not by the number
that succeeded, so failures push every frequency down slightly rather than
being quietly excluded.

If many fail, the data are too thin for the current settings: reduce `n_bins`,
reduce `max_indegree`, or drop a layer for that variant.

### Learning takes far too long

Cost is dominated by `bootstrap.n`, roughly linearly. Set it to 10 while
setting things up and raise it only for the run you report. `use_tabu: false`
is faster and searches less thoroughly.

Progress is printed with an estimated finishing time, so you can judge from the
first few resamples whether to stop and lower the count.

---

## Scenarios and the knob sweep

### `ValueError: No evidence could be applied for profile(s) ['Higher risk profile']`

None of the variables in that profile could be matched, so the profile would
have been an empty query. Usually one of:

- the variable is in a layer excluded by this variant, so it is not in this
  network at all;
- the value does not match any state, for instance `SEX: F` where the states
  are `Female` and `Male`.

The message immediately above it lists each rejected variable with the states
that were available.

### `profile — snapped to bins: AGE: 60 -> (45;64.675[`

Not a problem, but worth reading. It shows which bin your value landed in. If
`AGE: 65` falls in `[64.6;69.8[` and you meant "a young participant", the bin
boundaries are not where you assumed.

### `WARNING: base_profile fixes ['BASELINE TEST SCORE'], which lie downstream of 'MEASUREMENT A'`

The knob influences the outcomes through the variables between them. Holding
one of those fixed blocks that pathway, and the sweep will look flat because
the effect has been conditioned away rather than because it is absent.

Hold constant only variables upstream of the knob, typically demographics.

### `RuntimeError: No valid scenarios were produced — check base_profile.`

Every resample rejected the evidence. Almost always a variable name or value
that does not exist in the network. Check the rejection list printed above it.

### The sweep is flat

Three possibilities, in the order worth checking:

1. A mediator is fixed in `base_profile`. The warning above would have said so.
2. The knob genuinely carries no information about that outcome given the
   profile. A flat line with a narrow interval is a real result.
3. The knob's bins are too coarse to separate anything. Check `study.bins(...)`.

---

## Results

### An arc I expected is missing

Check, in this order:

1. Does the layer order permit it? An arc from a later layer to an earlier one
   is forbidden by construction and will never appear, however strong the
   association.
2. Is it in `stable_edges` with a moderate frequency? Appearing in 40% of
   resamples but not in the single network is common and is not a
   contradiction.
3. Are both variables binned finely enough to show the relationship?

### `In network` disagrees with a high frequency

Expected. One is the arc in the network learned from the full data; the other
is how often it survives resampling. Report the frequency.

### Mutual information is negative, like `-3.1e-16`

Floating-point error in summing over the joint distribution. Mutual information
cannot be negative. Values that small are rounded to zero in the table.

### `CMI` is empty for some variables

Those are the target's parents. They make up the conditioning set, so
conditional mutual information is not defined for them. The `Is parent` column
marks them.
