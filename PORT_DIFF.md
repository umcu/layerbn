# PORT_DIFF — HBC notebook functions vs `core/`

Branch: `port/hbc-onto-core`. Written **before** any code was changed.

Every function defined in `projects/HBC/00_preprocess.ipynb` and
`projects/HBC/01_bayesian_network.ipynb` that has a counterpart in `core/`,
compared line by line.

Verdicts:

- **identical** — same statements, same behaviour.
- **cosmetic** — differs only in naming, formatting, type hints, docstrings,
  or a strictly-internal detail with no observable effect.
- **behavioural** — could produce a different result.

Rule applied: where behaviour differs, **the notebook is authoritative** and
`core/` is changed to match. Exceptions are flagged explicitly below and in
the final report.

---

## Summary

| Verdict | Count |
| --- | --- |
| identical | 8 |
| cosmetic | 9 |
| behavioural → `core/` updated | 4 |
| behavioural → **not ported**, notebook keeps its own copy | 3 |
| no counterpart → untouched | 8 |

---

## `00_preprocess.ipynb`

### 1. `PreprocessConfig` (cell 3) ↔ `core.config.PreprocessConfig`
**Verdict: behavioural in general — equivalent at this call site. PORT.**

| | notebook | core |
| --- | --- | --- |
| `raw_dir` / `output_dir` | optional, default `project_root/"data"` | required |
| `codebook_path` | default `project_root/data/meta/HBC_CODEBOOK_LABELS.xlsx` | optional, `None` |
| `project_root` | `.resolve()` | `.expanduser()`, `.resolve()` only if relative |
| relative sub-paths | left as-is | resolved against `project_root` |

The notebook's only construction (cell 4) passes `project_root`, `raw_dir`,
`output_dir`, `codebook_path`, `risk_region` and `seed` explicitly, all
already absolute and `.expanduser()`-ed, and `project_root` is already
`.resolve()`-d at the call site. Every defaulting and resolution branch that
differs is therefore dead for this notebook. Same object either way.

### 2. `PreprocessConfig.apply_overrides` (cell 3) ↔ `core.config.apply_overrides`
**Verdict: no call sites. Dropped, not ported.**
The notebook never calls it (cell 4 constructs the config directly). Removed
along with the class definition; `core`'s module-level function is not
imported because nothing would use it.

### 3. `score2` (cell 6) ↔ `core.risk_scores.score2`
**Verdict: cosmetic. PORT.**
The notebook uses a 16-branch `if/elif` chain for the calibration constants;
`core` uses a `_CALIBRATION` dict keyed by `(age_band, region, gender)`.
All 99 numeric literals in the notebook version appear in `core` with
identical values (verified by multiset comparison of every float literal;
`core`'s only extras are `5.0/10.0/15.0` written as floats where the
notebook writes `5/10/15`, and `10.1093` from the DOI in `core`'s
docstring). Linear predictors, baseline survivals (`0.9605`, `0.9776`,
`0.7576`, `0.8082`), the over-70 shifts (`0.0929`, `0.2290`) and the
`classify` thresholds are byte-identical.

Minor: notebook `if np.isnan(risk)` vs core `if risk is None or np.isnan(risk)`
— core is a superset guard, unreachable difference.

### 4. `read_sav` (cell 8) ↔ `core.io.read_sav`
**Verdict: cosmetic. PORT.** core wraps in `Path(path)` and passes
`str(path)` to pyreadstat. Same result.

### 5. `apply_value_labels` (cell 8) ↔ `core.io.apply_value_labels`
**Verdict: cosmetic. PORT.** Identical except core's
`getattr(meta, "variable_value_labels", {}) or {}` (extra `or {}` guards a
`None` attribute). Same result.

### 6. `coalesce` (cell 8) ↔ `core.preprocess.coalesce`
**Verdict: identical. PORT.**

### 7. `to_datetime` (cell 8) ↔ `core.preprocess.to_datetime`
**Verdict: identical. PORT.**

### 8. `map_cdr_values` (cell 8)
No counterpart in `core/`. **Untouched.**

### 9. `contains_any` — nested inside `build_outcomes` (cell 10) ↔ `core.preprocess.contains_any`
**Verdict: behavioural. NOT PORTED — notebook keeps its own copy.**

```python
# notebook (nested)                     # core (module level)
series.fillna("").str.contains(...)     if series is None: return pd.Series(False)
                                        series.fillna("").astype(str).str.contains(...)
```

Two differences:
1. `None` input — the notebook raises `AttributeError`; core returns a
   **length-1** `Series([False])`. Call sites pass `outcomes.get(...)`, so if
   a cause-of-death column were ever missing, core would silently broadcast a
   length-1 Series into a length-N `np.where(...)`, changing the MACE and
   stroke flags instead of failing loudly.
2. `.astype(str)` — core coerces; the notebook relies on the column already
   being object dtype.

Swapping this in would change failure behaviour on exactly the columns that
define the outcomes. Left alone.

### 10. `normalise_string_categories` (cell 13) ↔ `core.preprocess.normalise_string_categories`
**Verdict: identical. PORT.**

### 11. `translate_labels` (cell 13) ↔ `core.preprocess.translate_labels`
**Verdict: cosmetic body, different signature. PORT + one added argument.**

Bodies are the same operation:
```python
# notebook                                    # core
df[column] = series.where(mapped.isna(), mapped)   df[column] = series.where(
df[column] = df[column].astype("category")             mapped.isna(), mapped).astype("category")
```
The notebook's version takes `(df)` and closes over the module-level
`LABEL_TRANSLATION`; core's takes `(df, label_map)`. Porting therefore
requires passing `LABEL_TRANSLATION` explicitly at both call sites
(cell 15 inside `build_baseline_table_by_group`, and cell 20). The mapping
itself stays in the notebook, where it belongs. **This is the only call-site
signature change in `00_preprocess.ipynb`.**

### 12. `enforce_domain_categories` (cell 13)
No counterpart. **Untouched.**

### 13. `impute_dataframe` (cell 15) ↔ `core.preprocess.impute_dataframe`
**Verdict: identical. PORT.**
Statement-for-statement the same, including the deprecated
`pd.api.types.is_categorical_dtype`. core restructures
`if series.isnull().any():` into an early `continue` (same control flow) and
gives `seed` a default of `1234`. The call site
`impute_dataframe(df_clean_reduced, config.seed)` passes it positionally, so
the default is never used.

### 14. `_normalize_label` (cell 15) ↔ `core.tables._normalize_label`
**Verdict: behavioural. → `core/` UPDATED to match the notebook.**

The notebook additionally returns `None` for the *strings* `"nan"`, `"none"`
and `"<na>"`:
```python
s = str(value).strip().casefold()
return None if s in {"nan", "none", "<na>"} else s
```
This matters because cell 19 title-cases every object column
(`col.astype(str).str.title()`), turning real `NaN` into the string
`"Nan"`. Without this guard those rows are counted in the denominator of
every percentage in the baseline table. The notebook's behaviour is the
published one.

### 15. `_format_median_iqr` (cell 15) ↔ `core.tables.format_median_iqr`
**Verdict: identical. PORT** (imported under the notebook's `_`-prefixed name
so the four call sites are unchanged).

### 16. `_format_count_pct` (cell 15) ↔ `core.tables.format_count_pct`
**Verdict: behavioural. → `core/` UPDATED to match the notebook.**

```python
# notebook — prefix match          # core — exact set membership
any(v.startswith(p) for p in ...)  normalized.isin(target_norms)
```
The notebook's category tables depend on prefix semantics:
`("Yes, with lifestyle advice", ["ja, met leefstijl"])` must match
`"Ja, Met Leefstijladvies"`, and `_format_count_pct(gdf.get("SEX"),
["male", "man", "m"])` relies on `"m"` matching as a prefix. Exact matching
would report `0 (0.0)` for most rows of the baseline table.

`core`'s exact-match version is dead code today (nothing imports
`build_grouped_table`), so changing it has no other consumers.

### 17. `_build_group_sequence`, `_add_category_rows`, `build_baseline_table_by_group` (cell 15) ↔ `core.tables.build_grouped_table` / `category_rows` / `Row`
**Verdict: structurally different. NOT PORTED.**

`core` models a table as a list of `Row` specs rendered by
`build_grouped_table`; the notebook builds `rows: list[dict]` imperatively
with a mix of `add_simple_row(metric, lambda gdf: ...)` closures and
`_add_category_rows`. Converting would mean rewriting all 14 row definitions
into `Row(...)`/`category_rows(...)` objects — a rewrite of the table, not an
import swap, with no way to verify equivalence without running the data.
Left as-is; only its three leaf formatters (#14–#16) were shared.

### 18. `build_outcomes`, `prepare_subset`, `harmonise_columns` (cells 10, 12)
No counterparts in `core/`. **Untouched.**

---

## `01_bayesian_network.ipynb`

### 19. `dict2html` (cell 3)
No counterpart. Also unused. **Untouched.**

### 20. `format_label` (cell 23) ↔ `core.discretisation.format_bin_label`
**Verdict: cosmetic for the inputs it receives. PORT** (aliased to
`format_label`).

```python
# notebook                                  # core
parts = label.strip('([)').split(';')       match = _INTERVAL_RE.match(label.strip())
lower = float(parts[0])                     if not match: return label
upper = float(parts[1].replace('[','')...)  lower = round(float(match.group(1)), decimals)
return f"({round(lower,1)};{round(upper,1)}["
```
Same output for every interval label. They differ only on non-interval
labels, where the notebook raises and core returns the input unchanged —
and the call site is already guarded by
`if all((";" in label and "[" in label) for label in labels)`, so that
branch is unreachable. `format_bin_label(label, decimals=1)` matches the
notebook's hardcoded `round(..., 1)`.

### 21. `configure_guided_structure` (cell 30) ↔ `core.bn_utils.configure_guided_structure`
**Verdict: two differences — one cosmetic, one behavioural-in-general but
provably equivalent for HBC. PORT; `core` NOT changed.**

**(a) `enforce` parameter — cosmetic.** The notebook's function takes
`enforce=True` and returns early when false; `core` has no such parameter
because its `build_bn` branches at the call site instead. Same reachable
behaviour.

**(b) how `true_outcomes` is derived — behavioural in general:**
```python
# notebook                                          # core
[var for var in outcomes                            [v for v in outcomes
 if "DROPOUT" not in var.upper()]                    if v not in dropout_vars]
```
For HBC these coincide exactly. The dropout layer `"L9 – Dropout"` contains
exactly `["DROPOUT REASON"]`, and every `outcomes` list passed in this
notebook is a subset of
`{"OUTCOME_CDR_INCREASE", "OUTCOME_MACE", "DROPOUT REASON"}`. The notebook's
rule drops `"DROPOUT REASON"` (substring `DROPOUT`); core's rule drops it
(member of `dropout_vars`); neither drops the two `OUTCOME_*` names. Identical
`true_outcomes`, hence identical forbidden arcs and identical post-learn arcs.

**I did not propagate the notebook's rule into `core`.** Doing so would
replace a structural test with a substring test that misclassifies any
cohort with a variable whose name happens to contain `DROPOUT`, and it
cannot change the HBC result. Flagged for your decision — say the word and
I will change it.

**(c) `allowed_arcs` membership test — cosmetic (performance).** The notebook
keeps a `list` and tests `(parent, child) not in allowed_arcs` (O(n) scan);
core builds a `set` first. Same membership, ~25× fewer comparisons.

### 22. `build_bn` (cell 30) ↔ `core.bn_utils.build_bn`
**Verdict: behavioural at the defaults. PORT + one added keyword argument at
every call site.**

| | notebook | core |
| --- | --- | --- |
| excluded layer | **hardcoded** `'L4 – Potential disease process markers'` | `exclude_layers=()` parameter |
| max indegree | hardcoded `5` | `max_indegree=5` default |
| outcome/dropout layer detection | hardcoded `"Outcomes" in k or "Dropout" in k` | `outcome_patterns=("Outcomes",)`, `dropout_patterns=("Dropout",)` defaults |
| post-learn arc failure | `except gum.InvalidArgument` | `except Exception` |
| `drop_outcomes` construction | `list(set(flat) - set(outcomes))` | list comprehension preserving layer order |

The L4 exclusion is the one that matters: `core`'s default excludes
**nothing**, so calling it unchanged would learn the network over six extra
biomarker variables. To preserve the published analysis, every call site that
previously relied on the hardcode now passes
`exclude_layers=HBC_EXCLUDE_LAYERS`, a constant defined in the cell that
previously held the `build_bn` definition. Everything else about the calls is
unchanged.

`drop_outcomes` ordering is irrelevant: it feeds `df.drop(columns=...)`,
which preserves the frame's own column order. `except Exception` is broader
than `except gum.InvalidArgument` — for HBC the arcs are valid, so neither
handler fires.

### 23. `bootstrap_edge_frequencies` (cells 33 **and** 70 — two byte-identical copies) ↔ `core.bn_utils.bootstrap_edge_frequencies`
**Verdict: behavioural. → `core/` UPDATED to match the notebook.**

```python
# notebook                                    # core (before)
count / n_bootstraps                          count / (successes or 1)
```
When a resample fails to fit, core reported a **higher** frequency than the
notebook — and it is the notebook's numbers that appear as the `f=NN%` arc
labels in the manuscript figures. core now divides by `n_bootstraps`.

Also: the notebook calls `random.seed(seed)` / `np.random.seed(seed)` before
each resample; core does not. No effect — the resample itself is
`df.sample(..., random_state=seed)`, and `build_bn` re-seeds both generators
on entry.

Signature: notebook is positional-friendly, core is keyword-only after `df`
and absorbs `score` / `use_tabu` into `**build_kwargs` for forwarding. Both
call sites (cells 34, 71) already pass everything by keyword, so they are
compatible unchanged apart from the `exclude_layers` addition on cell 34.

### 24. `build_bn_biomarkers` (cell 61) ↔ `core.bn_utils.build_bn`
**Verdict: behavioural. NOT PORTED — notebook keeps its own copy.**

It is `build_bn` with (i) no layer exclusion and (ii) **no post-learn
outcome→dropout `addArc` block**. `core.build_bn` couples the arc
constraints to that block: `enforce_structure=True` applies the layered
forbidden arcs *and* forces the outcome→dropout arcs in afterwards;
`enforce_structure=False` does neither.

There is no argument combination that reproduces
`build_bn_biomarkers`: the biomarker ablation network is learned **with** the
layer constraints but **without** the forced arcs. Porting it would require a
new parameter on `core.build_bn` (e.g. `force_selection_arcs: bool`), which is
a change to `core`'s behaviour surface rather than a like-for-like swap.
Left as a local definition; see the final report.

### 25. `bootstrap_scenario_risks` (cell 85) ↔ `core.bn_utils.bootstrap_scenario_risks`
**Verdict: cosmetic body, one hardcode lifted to a parameter. PORT + added
arguments.**

Bodies match statement for statement (resample → fit → `LazyPropagation` →
`setEvidence` → `posterior` → mean/std/2.5%/97.5% quantiles → sorted frame).
core writes `ie.setEvidence(dict(evidence))` and hoists
`outcome_labels = dict(target_outcomes)` out of the loop; same values.

The one real difference: the notebook hardcodes
`outcomes=['OUTCOME_CDR_INCREASE', 'OUTCOME_MACE', 'DROPOUT REASON']` **inside**
the function; core takes `outcomes_for_learning`. The call site now passes
that exact list, plus `exclude_layers=HBC_EXCLUDE_LAYERS` (previously implied
by `build_bn`'s hardcode).

### 26. `_state_for_value` (cell 93) ↔ `core.discretisation.state_for_value`
**Verdict: identical. PORT.** Same regex, same exact-match-first rule, same
clamping to the end bins, same `None` returns. Differs only in local variable
names (`v` → `numeric`, `m` → `match`) and in compiling the pattern at module
scope instead of per call.

### 27. `_descendants` (cell 93) ↔ `core.bn_utils.descendants`
**Verdict: identical. PORT.**

### 28. `_reduced_frame` (cell 93) ↔ `core.bn_utils._reduced_for_template`
**Verdict: same as #22 — L4 hardcoded vs parameter. PORT (indirectly).**
Private to `bootstrap_knob_sweep`; the notebook's direct call disappears with
the local definition. `core` reproduces it as long as `exclude_layers` is
forwarded, which `bootstrap_knob_sweep` does via
`build_kwargs.get("exclude_layers", ())`.

### 29. `bootstrap_knob_sweep` (cell 93) ↔ `core.bn_utils.bootstrap_knob_sweep`
**Verdict: cosmetic body, hardcodes lifted to parameters. PORT + added
arguments.**

Same fixed template, same reference network, same evidence
resolution/`snapped`/`rejected` reporting, same mediator (descendant) warning,
same `applied_idx` state-index evidence, same bootstrap loop, same
`P`/`CI_low`/`CI_high` frame, same `RuntimeError` when no rows are produced.
core adds `verbose: bool = True` (default reproduces the notebook's prints)
and replaces the internal `_LEARN_OUTCOMES` with `outcomes_for_learning`.
Both `fixed_template=...` and `use_smoothing=True` are set identically.

### 30. `plot_knob_sweep` (cell 93) ↔ `core.plotting.plot_knob_sweep`
**Verdict: cosmetic. PORT.** Machine-diffed: the only differences are line
wrapping, two local renames (`s_label` → `state`, `color` → `colour`), type
hints, and the docstring. Palette, colour cycle, `alpha=0.16`, `lw=2.7`,
`ms=8`, the `"Yes"`-only annotation, axis limits (`top * 1.20`), legend
placement and `suptitle` text are identical.

---

## Duplicated logic that is *not* a function definition

Flagged for completeness; **not changed**, because replacing an inline
expression with a call would edit analysis cells without reducing any
duplication of *definitions*.

| Notebook | `core/` equivalent | Note |
| --- | --- | --- |
| cell 21 `type_processor = DiscreteTypeProcessor(defaultDiscretizationMethod="quantile", defaultNumberOfBins=4, discretizationThreshold=10)` | `core.discretisation.make_type_processor(method="quantile", n_bins=4, threshold=10)` | Constructs an identical object. The parameters are an analysis choice that must stay in the notebook either way. |
| cells 32, 68–69 — `layer_color_map` built from `min_color_val`/`max_color_val`/`steps`, then `node_colors` looped over `layer_map` | `core.plotting.default_layer_colors` + `build_node_colors` | Identical arithmetic (`0.111111`, `0.99999`, `len-1` steps) and identical fallback `0.5`. Note the notebook computes this **twice** with two different `layer_order` lists (cell 68 inserts `'L3 – Specialized biomarkers'`), which is a real inconsistency but a pre-existing one. |

---

## Changes made to `core/` (rule: notebook wins)

| ID | File | Change |
| --- | --- | --- |
| C1 | `core/bn_utils.py` | `bootstrap_edge_frequencies` denominator `successes` → `n_bootstraps` (#23) |
| C2 | `core/bn_utils.py` | `build_bn`: fix reversed tuple unpacking in the `enforce_structure=False` branch so both branches return `(dropout_vars, true_outcomes)` as the notebook does |
| C3 | `core/tables.py` | `format_count_pct`: exact match → prefix match (#16) |
| C4 | `core/tables.py` | `_normalize_label`: return `None` for `"nan"` / `"none"` / `"<na>"` (#14) |

C2 detail — `core` currently binds the pair backwards when
`enforce_structure=False`, because `collect_outcome_vars` returns
`(outcome_vars, dropout_vars)`:

```python
dropout_vars, true_outcomes = configure_guided_structure(...) \
    if enforce_structure else collect_outcome_vars(...)   # ← swapped
```

Unreachable in this notebook (every call uses `enforce_structure=True`), but
it is a divergence from the notebook's contract and a trap for the next edit.
