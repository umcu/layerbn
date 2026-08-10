# Migration plan: splitting VCI-Bayes into a package + analysis repos

Status: assessment only. Nothing in this document has been implemented.
Written against the working tree at commit `d421e13` (branch `main`).

---

## 0. Verdict first

Three findings dominate everything below.

**(a) `core/` currently has zero real users.** The HBC notebooks — the only
analysis in this repo that has ever produced results — do not import `core/`
at all. Verified:

```
$ grep -o "[a-z_]*core\.[a-z_]*" projects/HBC/*.ipynb | sort -u
projects/HBC/01_bayesian_network.ipynb:core.display     # IPython.core.display
... (no `from core...` anywhere)
```

`core/bn_utils.build_bn` is a *re-typed copy* of the notebook's `build_bn`,
never run against real data, never diffed against the notebook's output. The
only files that import `core/` are `projects/_TEMPLATE/*.ipynb` and its two
copies — which are byte-identical to the template except for the title line,
and whose first executable cell is `raise NotImplementedError`. There are no
tests and no CI (`find . -name tests -o -name .github` → nothing).

So the package you want to publish is, today, ~1,470 lines of unvalidated
code. **Step 1 of any migration is porting HBC onto `core/` and diffing the
learned structure, edge frequencies and posteriors against the manuscript
figures.** Until that diff is clean, nothing else is worth doing.

**(b) The reusable-machinery fraction is real but smaller than it looks, and
it is concentrated in the modelling half.** Detail in §7. Short version:
~30% of the lines are reusable machinery, ~90% of the *decisions* are
per-cohort — but the modelling-side decisions (layers, bins, edge policy)
are exactly the kind of thing YAML expresses well, while the
preprocessing-side decisions (outcome derivation, censoring, dropout
canonicalisation) are not expressible in config at any reasonable cost. The
config-driven design is right **only if you scope the package to start at an
analysis-ready dataframe** and explicitly refuse to own preprocessing.

**(c) An R user does not need to reimplement much, because `bnlearn` already
has it.** `bnlearn::tiers2blacklist()` is the layer-ordering constraint;
`bnlearn::boot.strength()` is the bootstrap edge-frequency analysis;
`gRain` is the inference. Detail in §8. This should change what you think
the citable artefact *is*: the durable contribution is the **spec + the
dropout/censoring convention**, not the Python. Version the schema as the
primary contract.

---

## 1. Inventory of `core/`

1,467 lines across 9 modules. Classification: **(a)** genuinely general,
**(b)** HBC logic that leaked in, **(c)** dead.

### `core/__init__.py` — 19 lines — (c) dead

Docstring only, plus `__version__ = "0.1.0"`. Deliberately re-exports
nothing. Fine as a decision, but it means `import vcibayes` gives a user
nothing, which is hostile for a package whose selling point is a small public
API. Replace with explicit re-exports (§3).

### `core/io.py` — 58 lines — (a) general

`read_sav`, `apply_value_labels`, `read_parquet`, `write_parquet`.
Depends: `pandas`, `pyreadstat`, `pathlib`.
Thin, correct, cohort-agnostic. **But it does not belong in a Bayesian-network
package** — `pyreadstat` is a heavyweight dependency (SPSS) carried for four
lines of convenience. Move to the analysis repos or make it an
`[spss]` extra.

### `core/config.py` — 108 lines — (a) general with one (b) leak

`PreprocessConfig` dataclass + `load_project_config` + `apply_overrides`.
Depends: `pyyaml`, `pathlib`.

- Leak: `risk_region: str = "Low"` is a SCORE2 field sitting in the generic
  config dataclass. A cohort that never computes SCORE2 still gets it.
- `apply_overrides` (lines 98–108) is called by nothing — dead.
- The whole module is superseded by the spec loader in §4. `PreprocessConfig`
  is a *paths* config; the package needs a *model* spec. Keep the YAML-loading
  idea, discard this dataclass.

### `core/discretisation.py` — 98 lines — (a) general

`make_type_processor`, `format_bin_label`, `state_for_value`,
`describe_template`.
Depends: `pyagrum.lib.discreteTypeProcessor` (lazy), `pandas`, `re`.

Genuinely reusable, and `state_for_value` (resolving `AGE=72` to the bin
`[68.05;73.63[`) is one of the few pieces of non-obvious value here.

Design smell that must be fixed before publishing: **bin edges are only
recoverable by regex-parsing pyAgrum's label strings** (`_INTERVAL_RE`,
line 35). The numeric edges are the scientific content; the string form is
an implementation detail of one engine. The package must emit explicit
numeric edges in its output manifest (§4 `output.manifest`), or
cross-engine reproducibility (§8) is impossible and the labels are one
pyAgrum release away from breaking.

### `core/preprocess.py` — 113 lines — mixed

`coalesce`, `to_datetime`, `normalise_string_categories`, `translate_labels`,
`impute_dataframe`, `contains_any`.
Depends: `pandas`, `numpy`, `sklearn` (IterativeImputer).

- `coalesce`, `to_datetime`, `normalise_string_categories`, `translate_labels`,
  `contains_any` — (a) general, but they are four-line pandas idioms. They
  are not worth a dependency, and `contains_any` is imported by the template
  and never called (dead).
- `impute_dataframe` — (a)/(b) borderline. The *mechanism* (IterativeImputer
  for numeric, mode for categorical) is general; the *policy* is a
  judgement call that HBC made and that silently propagates. It will happily
  impute an outcome column, which changes the estimand. The package version
  must refuse to impute variables with `role: outcome` unless forced.
- `pd.api.types.is_categorical_dtype` (line 92) is deprecated in pandas 2.2
  and removed in 3.0. Will break.

Recommendation: keep only `impute_dataframe` (hardened), drop the rest.

### `core/risk_scores.py` — 191 lines — (a) general, wrong package

`score2` — SCORE2 2021 (Hageman et al.), a faithful port of
`RiskScorescvd::SCORE2`. Depends: `numpy`, `logging`. Correct, well-commented,
coefficients cited.

It has nothing to do with Bayesian networks. Shipping it inside the citable
BN artefact means every reviewer question about SCORE2 calibration lands on
the BN package. Imported by nothing (the template has it commented out).
**Move to the HBC analysis repo**, or publish as a separate 200-line package
if other groups want it.

### `core/inference.py` — 77 lines — (a) general

`mutual_information_scores`, `conditional_mutual_information_scores`.
Depends: `pyagrum` (lazy), `pandas`.
Clean generalisation of four near-identical notebook cells (HBC cells 52, 54,
56, 58). Keep essentially as-is; add the ranking to a DataFrame with the
conditioning set recorded, not just a Series name.

### `core/plotting.py` — 156 lines — mixed

- `default_layer_colors`, `build_node_colors` — (a) general, ~35 lines.
- `show_and_save_bn` — (a) general, but conflates "show in notebook" with
  "export a file"; the `show=` flag plus `**kwargs` forwarded to two
  different pyAgrum APIs is fragile. Rewrite.
- `plot_knob_sweep` — **(b) HBC-specific.** Lines 98 and 127 hardcode
  `{"No", "Unobserved", "Yes"}` as the palette keys and annotate only the
  state literally named `"Yes"`. Those are HBC's outcome state labels. Any
  other cohort gets a grey fallback cycle and no annotations. Parameterise
  `palette=` and `annotate_state=`.

Missing from this module, and needed (see §2): arc widths from mutual
information, and arc colour/label from bootstrap frequency. Those exist only
in the notebook.

### `core/tables.py` — 165 lines — (a) general, (c) dead, and already drifted

`Row`, `build_grouped_table`, `category_rows`, `format_median_iqr`,
`format_mean_sd`, `format_count_pct`. Depends: `pandas`.

A tidy generalisation of HBC's `build_baseline_table_by_group`. Nothing
imports it — not even the template notebooks. Dead.

It has also **already diverged from the code it generalises**:
`core/tables.py::format_count_pct` matches category labels by exact
casefolded equality, whereas `projects/HBC/00_preprocess.ipynb` cell 15 was
subsequently fixed to match by *prefix* precisely because exact matching
failed on Dutch variants (`"Ja, met leefstijladvies"` vs
`"Ja, Met Leefstijladvies"` after title-casing). `core/` is one commit behind
the analysis it claims to generalise, and nobody noticed because nothing runs
it. This is the clearest evidence for finding (a) above.

"Table 1" is not a Bayesian-network concern. **Move to the HBC repo** (or a
separate `tableone`-style package — several already exist).

### `core/bn_utils.py` — 482 lines — the actual package, with bugs

`collect_outcome_vars`, `configure_guided_structure`, `build_bn`,
`bootstrap_edge_frequencies`, `bootstrap_scenario_risks`, `descendants`,
`bootstrap_knob_sweep`, `_reduced_for_template`.
Depends: `pyagrum` (lazy), `pandas`, `numpy`, `core.discretisation`.

This is where the reusable value is. It is also where the HBC assumptions are
most deeply baked in, and it contains at least three defects that need
fixing before publication:

1. **Layer semantics are stringly typed.** `DEFAULT_OUTCOME_LAYER_PATTERNS =
   ("Outcomes",)` and `DEFAULT_DROPOUT_LAYER_PATTERNS = ("Dropout",)`
   (lines 22–23) are HBC's layer names promoted to library defaults. A layer
   called `"Outcomes of imaging"` is silently classified as an outcome layer;
   a variable named `DROPOUT_ADJUSTED_SCORE` is silently excluded from
   `true_outcomes` by the notebook's `"DROPOUT" not in var.upper()`. This is
   **(b)** and must become an explicit `role:` field (§4).

2. **Tuple-swap bug**, lines 187–193. When `enforce_structure=False`:
   ```python
   dropout_vars, true_outcomes = configure_guided_structure(...) \
       if enforce_structure else collect_outcome_vars(...)
   ```
   but `collect_outcome_vars` returns `(outcome_vars, dropout_vars)` — the
   two names are bound backwards. Currently harmless only because the block
   that consumes them is guarded by `if enforce_structure:`. It is a live
   trap for the next edit.

3. **`_reduced_for_template` ignores the caller's patterns**, line 480:
   `collect_outcome_vars(layer_map)` is called with *default* patterns even
   when the caller passed custom `outcome_patterns` / `dropout_patterns` to
   `build_bn`. The template will then be built over a different column set
   than the networks, so the "fixed template across bootstraps" guarantee
   silently fails for any non-HBC cohort.

4. **Silent behaviour change vs. the published analysis.**
   `bootstrap_edge_frequencies` divides counts by `successes` (line 245);
   the notebook divides by `n_bootstraps` (cell 33, line 833). If any
   resample fails, `core/` reports *higher* edge frequencies than the
   manuscript. Whichever is correct, it must be a documented, tested choice —
   and the HBC re-run in step 1 will not reproduce the published `f=NN%`
   arc labels if failures occurred.

5. **Post-hoc `bn.addArc` after `learnBN`**, lines 198–207. Outcome→dropout
   arcs are forced in *after* structure learning and parameter estimation.
   Verify what pyAgrum does to the child's CPT when a parent is added to an
   already-parameterised BN — if the CPT is resized without re-estimation,
   every posterior read off `DROPOUT REASON` (and anything downstream) is
   computed from an unparameterised table. This is worth checking before the
   HBC manuscript goes out, independently of the migration. The fix is to
   express these as *required* arcs (a whitelist) handed to the learner, not
   as surgery afterwards — which the spec in §4 does via `edges.required`.

Everything else in the module — the layer→forbidden-arc expansion, the
bootstrap loops, the mediator/overadjustment check in `bootstrap_knob_sweep`,
the CI summarisation — is **(a)** genuinely general and is the core of what
you should publish.

### Non-`core/` dead weight

| Path | Verdict |
| --- | --- |
| `config/global.yml`, `config/global.dcf` | R `ProjectTemplate` config (`libraries: reshape2, plyr, tidyverse`, `cache_file_format: RData`). Nothing in this repo is R. **Delete.** |
| `config/data_paths.example.yml` | Superseded by per-project `config.yml`; only `preprocess_data.py` still looks for `config/data_paths.yml`. Delete with the script. |
| `concept/00_main_concept.ipynb` | 1 cell, 0 code cells. Empty. Delete or write it. |
| `pyproject.toml` `packages = ["core"]` | Publishing a top-level module named `core` is a name collision waiting to happen. Rename to `vcibayes`. |

---

## 2. Notebook-only logic, per notebook

### `projects/METAVCI_COGNITION/*` and `projects/METAVCI_WMH_BLOOD/*`

**Nothing.** Verified by cell-by-cell diff against `projects/_TEMPLATE/`: all
four notebooks are identical to the template except the first markdown line
(`# Preprocessing pipeline` → `# METAVCI_COGNITION — preprocessing pipeline`).
`00_preprocess.ipynb` cell 7 is `raise NotImplementedError`. There is no
analysis to migrate; there are two empty folders.

This matters for the plan: you are not migrating three cohorts. You are
migrating **one** (HBC), and the other two are unwritten. Which also means
the `_TEMPLATE`-copy pattern has already failed once — two copies were made,
neither was filled in, and both now silently lag any change to `core/`.
Replace copy-paste scaffolding with a generator (`vci-bayes init`) that pins
a package version.

### `projects/HBC/01_bayesian_network.ipynb` (98 cells, ~1,945 code lines)

Logic that exists **only** here and must move into the package for a
notebook-free run:

| # | Logic | Cells | Destination |
| --- | --- | --- | --- |
| 1 | `build_bn` + `configure_guided_structure` — the manuscript's actual learner, with `'L4 – Potential disease process markers'` hardcoded as the excluded layer | 30 | `fit()`; exclusion becomes `variants.include_layers` |
| 2 | `build_bn_biomarkers` — near-duplicate of (1) with no layer exclusion and a *different* smoothing rule (BIC branch enables smoothing inline) | 61 | `variants:` in the spec — this is the ablation workflow |
| 3 | **Arc widths from mutual information**: per-arc MI, `sqrt(mi)/sqrt(max_mi)*3.0 + 0.5`. Duplicated verbatim in 3 cells | 42, 66, 72 | `plot_network(arc_width="mutual_information")` |
| 4 | **Arc colour + `f=NN%` labels from bootstrap frequency**, incl. the name→node-id remap | 43–47, 67, 73, 75 | `plot_network(edge_stability=...)` |
| 5 | Node colours from an ordered `layer_order` list — **written out twice with different content** (cells 32 and 68, the latter inserting `L3 – Specialized biomarkers`) | 32, 68 | derived from spec layer order; never hand-listed |
| 6 | MI / conditional-MI ranking loops, print-formatted, **four near-identical copies** (CDR/MACE × raw/conditional) and three more for the biomarker network | 52–58, 80–82 | `information_ranking()` (already ported) |
| 7 | `bootstrap_edge_frequencies` — defined twice, identically, in cells 33 and 70 | 33, 70 | `bootstrap_edges()` |
| 8 | `bootstrap_scenario_risks` with `_LEARN_OUTCOMES` hardcoded *inside* the function body | 85 | `scenario_risks()` (ported; outcomes now a parameter) |
| 9 | `bootstrap_knob_sweep` + `_reduced_frame` + `_state_for_value` + `_descendants` + `plot_knob_sweep` | 93 | ported to `core/`; `_reduced_frame` hardcodes the L4 exclusion |
| 10 | Scenario evidence dicts (`healthy_evs`, `ill_evs`) + `LazyPropagation` + `showInference(evs=...)` + PDF export | 86–91 | `FittedNetwork.posterior()` + `plot_network(evidence=...)` |
| 11 | `gum.saveBN(bn_joint, "bn_joint.bifxml")` — writes to **cwd**, not to `output_dir` | 96 | `FittedNetwork.save()` |
| 12 | CPT display/export (`showTensor`, `sideBySide` of two CPTs) | 50, 59, 78, 79 | `FittedNetwork.cpt(var) -> DataFrame` + writer |
| 13 | `gum.config["notebook", "graph_layout"/"graph_rankdir"]` — global pyAgrum state | 4 | render options on `plot_network` |
| 14 | Config resolution: three candidate paths, a `Path(__file__)` guard that cannot work in a notebook, an unreachable `importlib` fallback, and a `DATA_DIR` existence fallback | 6 | `load_spec()` |

Logic here that must move **out** of analysis entirely, into preprocessing —
it is data cleaning masquerading as analysis:

- Cell 8: `STROKE HISTORY` / `CVA` blank-and-NaN → `'No'` / `'Nee'`. This
  edits the analysis dataset after imputation.
- Cell 17: patching `DROPOUT REASON`'s layer to `'L9 – Dropout'` — the
  **sixth** occurrence of this same patch across the codebase
  (`preprocess_data.py` lines 596, 1038, 1045, 1047, 1120, 1122, 1125 and
  this cell). It is a symptom of the codebook not carrying the role.

Logic here that should move to the **HBC analysis repo**, not the package:

- Cells 9–14: the dropout-by-group stacked bar and the ~250-line hand-rolled
  Bézier alluvial plot (`_draw_band`, `alluvial_plot`, `_luminance`). Nice
  figures, entirely HBC-shaped (T0/T2/T4, Dutch dropout categories).
- Cell 64: ~160 lines of statsmodels logistic regression (biomarker ORs,
  unadjusted + age/sex-adjusted). This is a different method that happens to
  live in the BN notebook.

### `projects/HBC/00_preprocess.ipynb` (24 cells, ~1,268 code lines) and `preprocess_data.py` (1,206 lines)

These two are ~90% duplicates of each other. `CONTRIBUTING.md` §9 states
"Both. … They share logic." **They do not share logic — they share
copy-paste, and they have diverged.** Differences found:

- The notebook writes `df_outcome_states.parquet` (cell 22); the script does
  not. `01_bayesian_network.ipynb` cell 11 loads that file. **The script
  cannot reproduce the analysis notebook's inputs.**
- The notebook fills 3 missing `DIABETES` and 2 missing `ROKEN` values with
  `"Nee"` before SCORE2 (cell 20); the script does not.
- The notebook resolves cholesterol column-name variants via `_find_col`
  (cell 20); the script hardcodes `CHOLESTEROL_TOTAAL` / `CHOLESTEROL_HDL`.
- The notebook's baseline-table category matching is prefix-based; the
  script's is exact-match (as is `core/tables.py`).

Whichever produced the manuscript numbers, the other two are wrong. Resolve
this before anything else, and delete the losers.

Cohort logic that lives here and would need to move somewhere (**not** into
the package — see §7):

| Logic | Lines | Notes |
| --- | --- | --- |
| `build_outcomes` — stroke/MACE derivation incl. Dutch cause-of-death substring lists (`myocardinfarct`, `hartstilstand`, `decompensatio`, …), CDR-increase rule, "Moved to Nursing Home ⇒ CDR increase" | ~290 | Pure cohort judgement, and the `Unobserved` encoding here *defines the estimand* |
| Dropout-reason canonicalisation — 6 numeric codes + ~20 Dutch free-text prefixes + `^([0-9])\s*=\s*(.*)$` | ~75 | Cohort-specific data entry archaeology |
| `prepare_subset` — codebook matching via `_E[0-9]+_C[0-9]+$` stripping; derived `SYS_BP`, `DIAS_BP`, `HV_ICV`, `TBV_ICV`, `CBF`; smoking backfill; `CAD`/`PAD`/`MACE` | ~90 | The derived-variable formulas are the interesting part (§5 gap 4) |
| `harmonise_columns`, `NAME_MAPPING`, `LABEL_TRANSLATION`, `EXTRA_LAYER_ROWS`, `enforce_domain_categories`, `BASELINE_CDR_CATEGORIES` | ~110 | Renaming/labelling; partly config-expressible (§5 gap 3) |
| `build_baseline_table_by_group` + 4 category-label tables | ~180 | HBC repo |
| Local copies of `score2`, `read_sav`, `apply_value_labels`, `coalesce`, `to_datetime`, `impute_dataframe`, `normalise_string_categories`, `translate_labels` | ~420 | Already in `core/`; delete after the port |

---

## 3. Proposed public API

Package `vcibayes`. Twelve names, one of which (`run`) does everything.
Users never touch anything else; there is no supported reason to subclass or
monkey-patch.

```python
# vcibayes/__init__.py
from vcibayes import (
    Spec, load_spec, validate,          # 1-3   spec
    fit, FittedNetwork,                 # 4-5   modelling
    bootstrap_edges,                    # 6     stability
    information_ranking,                # 7     interpretation
    scenario_risks, knob_sweep,         # 8-9   what-if
    plot_network, plot_knob_sweep,      # 10-11 figures
    run,                                # 12    the whole pipeline
)
```

```python
def load_spec(
    path: str | Path,
    *,
    overrides: Mapping[str, Any] | None = None,
) -> Spec:
    """Parse + schema-validate a YAML spec. `overrides` uses dotted keys
    (`{"model.seed": 7}`) so a CLI/sweep can vary one field."""


@dataclass(frozen=True)
class Spec:
    """Validated spec. Immutable — a run is reproducible from this object
    plus the input data."""
    spec_version: int
    name: str
    data: DataSpec
    layers: tuple[Layer, ...]          # ORDERED; order is the constraint
    edges: EdgePolicy
    discretisation: DiscretisationSpec
    model: ModelSpec
    variants: tuple[Variant, ...]
    analyses: AnalysisSpec
    output: OutputSpec

    @property
    def layer_map(self) -> dict[str, list[str]]: ...
    @property
    def variables(self) -> list[str]: ...
    def by_role(self, role: Role) -> list[str]: ...      # covariate|outcome|selection
    def for_variant(self, name: str) -> "Spec": ...      # resolved copy
    def to_yaml(self) -> str: ...


def validate(spec: Spec, df: pd.DataFrame) -> ValidationReport:
    """Check the spec against real data *before* a 40-minute bootstrap.
    Reports (never raises for warnings): columns in the spec missing from
    the data; columns in the data with no layer; a `role: outcome` layer
    that is not last; variables whose implied cardinality × parent
    cardinality will blow up the CPT; constant / near-constant columns;
    outcome columns containing NaN (would be imputed); required arcs that
    contradict the layer ordering."""


def fit(
    df: pd.DataFrame,
    spec: Spec,
    *,
    variant: str | None = None,
    template: Template | None = None,     # freeze bins across bootstraps
    seed: int | None = None,              # overrides spec.model.seed
) -> FittedNetwork:
    """Learn one network. Deterministic given (df, spec, seed)."""


class FittedNetwork:
    bn: Any                               # pyagrum.BayesNet — escape hatch
    spec: Spec
    template: Template
    variant: str

    def arcs(self) -> pd.DataFrame: ...            # parent, child, mi
    def cpt(self, variable: str) -> pd.DataFrame: ...
    def posterior(
        self,
        evidence: Mapping[str, Any],               # raw values; binned for you
        targets: Sequence[str] | None = None,
    ) -> pd.DataFrame: ...                         # + `.rejected` on the frame
    def bins(self) -> pd.DataFrame: ...            # variable, edges, labels
    def save(self, path: str | Path) -> Path: ...  # .bifxml + sidecar manifest
    @classmethod
    def load(cls, path: str | Path) -> "FittedNetwork": ...


def bootstrap_edges(
    df: pd.DataFrame,
    spec: Spec,
    *,
    variant: str | None = None,
    n: int | None = None,
    seed: int | None = None,
    n_jobs: int = 1,
    progress: bool = False,
) -> EdgeStability:
    """`.frame` → parent, child, frequency, n_success; `.n_failed`,
    `.failures` (exception messages, not printed). Denominator is
    `n_success` and is recorded — never silently `n`."""


def information_ranking(
    fitted: FittedNetwork,
    target: str,
    *,
    conditional: bool = False,
    conditioning_set: Sequence[str] | None = None,   # default: parents
    exclude: Sequence[str] = (),
) -> pd.DataFrame:                                    # variable, score, conditioned_on


def scenario_risks(
    df: pd.DataFrame,
    spec: Spec,
    profiles: Mapping[str, Mapping[str, Any]],
    targets: Sequence[str],
    *,
    n: int | None = None,
    seed: int | None = None,
) -> pd.DataFrame:      # scenario, outcome, state, mean, ci_low, ci_high, n_boot


def knob_sweep(
    df: pd.DataFrame,
    spec: Spec,
    knob: str,
    base_profile: Mapping[str, Any],
    targets: Sequence[str],
    *,
    n: int | None = None,
    seed: int | None = None,
) -> SweepResult:
    """`.frame`, `.meta`, `.warnings` — the mediator/overadjustment check
    returns structured warnings instead of `print()`ing them."""


def plot_network(
    fitted: FittedNetwork,
    *,
    edge_stability: EdgeStability | None = None,   # → arc colour + f=NN% labels
    evidence: Mapping[str, Any] | None = None,     # → inference rendering
    arc_width: Literal["mutual_information", "uniform"] | Mapping = "mutual_information",
    node_color_by: Literal["layer", "role", "none"] = "layer",
    path: str | Path | None = None,                # None = return figure only
    **render: Any,
) -> RenderResult


def plot_knob_sweep(
    sweep: SweepResult,
    *,
    palette: Mapping[str, str] | None = None,      # no hardcoded Yes/No/Unobserved
    annotate_state: str | None = None,
    path: str | Path | None = None,
) -> RenderResult


def run(
    spec: Spec | str | Path,
    data: pd.DataFrame | str | Path | None = None,
    *,
    outdir: str | Path | None = None,
    only: Sequence[str] | None = None,             # subset of analyses
) -> RunResult:
    """Execute every variant and analysis in the spec, write everything under
    `outdir`, and emit `manifest.json` (spec hash, data hash, package +
    pyagrum versions, seeds, per-variant timings, bin edges, failures).
    CLI equivalent: `vci-bayes run spec.yml --data df.parquet --out outputs/`."""
```

Plus exactly two **plugin points**, registered via entry points
(`vcibayes.discretisers`, `vcibayes.edge_rules`) so an analysis repo can
extend without forking:

```python
def register_discretiser(name: str, fn: Callable[[pd.Series, dict], BinEdges]) -> None
def register_edge_rule(name: str, fn: Callable[[Spec, pd.DataFrame], Iterable[Arc]]) -> None
```

`register_edge_rule` is what HBC's "arcs into the selection layer only from
outcomes" becomes if you decide it is too cohort-specific to be a built-in —
though §4 makes it declarative, which I prefer.

**Deliberately not in the public API:** `read_sav`, `score2`,
`build_grouped_table`, `impute_dataframe`, `coalesce`, `translate_labels`.
Those are preprocessing; see §7.

---

## 4. YAML spec schema

Design rules: layer **order** is the constraint (never re-sorted); roles are
explicit (`covariate` / `outcome` / `selection`) — never inferred from layer
names; everything that changes a number has a default that is written into
the output manifest.

### Schema

```
spec_version: int                      # 1
name: str
description: str?

data:
  path: str                            # relative to spec file
  format: parquet | csv | feather      # default: inferred from suffix
  id_columns: [str]?                   # excluded from learning
  select: [str]?                       # if omitted: every variable in layers
  filter: str?                         # pandas .query() expression

layers:                                # ORDERED list. Order = the constraint.
  - name: str
    label: str?
    role: covariate | outcome | selection    # default covariate
    variables: [str]

edges:
  layer_ordering: forward | none       # forward: parent layer <= child layer
  within_layer: allow | forbid         # default allow (HBC behaviour)
  between_outcomes: allow | forbid     # default forbid (HBC behaviour)
  selection_parents:                   # who may point at a `selection` layer
    from_roles: [outcome]              # default: [outcome]
    required: true                     # force these arcs into the whitelist
  forbidden:                           # explicit, beyond the layer rules
    - {from: str, to: str} | {from_layer: str, to_layer: str}
  required:                            # whitelist; validated against ordering
    - {from: str, to: str}
  max_indegree: int                    # default 5

discretisation:
  default: {method: quantile|uniform|kmeans|none, n_bins: int, threshold: int}
  per_variable:
    <VAR>: {method: quantile|uniform|kmeans|edges|none,
            n_bins: int?, edges: [float]?, labels: [str]?}
  freeze_across_bootstrap: bool        # default true
  never_discretise: [str]?

missing:
  impute: none | iterative_mode        # default none
  seed: int?
  never_impute_roles: [outcome, selection]   # default; imputing changes the estimand
  on_missing_outcome: error | keep      # default error

model:
  algorithm: tabu | greedy | miic       # default tabu
  score: K2 | BIC | BDeu                # default K2
  score_params: {ess: float}?           # BDeu only
  smoothing: auto | always | never      # auto = on for BIC
  seed: int                             # default 42
  bootstrap: {n: int, seed: int?}

variants:                               # optional; default a single "base"
  - name: str
    include_layers: [str]?              # default: all
    exclude_layers: [str]?
    outcomes: [str]?                    # subset of role:outcome variables

analyses:
  information: {targets: [str], conditional: bool}?
  scenarios: {profiles: {name: {var: value}}, targets: [str], bootstrap: int?}?
  knob_sweep: {knob: str, base_profile: {var: value}, targets: [str],
               bootstrap: int?, on_mediator: warn | error}?

output:
  dir: str
  figures: {formats: [pdf|png|svg], node_color_by: layer|role|none,
            arc_width: mutual_information|uniform,
            arc_label: bootstrap_frequency|none,
            cmap_node: str, cmap_arc: str, layout: dot, rankdir: TB}
  tables: {edge_frequencies: bool, information: bool, cpts: [str], format: csv|parquet}
  network: {formats: [bifxml|net|xdsl]}
  manifest: bool                        # default true
```

### Complete filled-in example — HBC, as actually run

```yaml
spec_version: 1
name: hbc-joint
description: >
  Heart-Brain Connection: layered Bayesian network for 4-year CDR increase
  and MACE, with dropout modelled explicitly as a selection layer.

data:
  path: ../data/df_imp.parquet
  format: parquet
  id_columns: [patientID]

layers:
  - name: L0
    label: Unmodifiable demographics
    role: covariate
    variables: [AGE, SEX]

  - name: L1
    label: Modifiable demographics / lifestyle factors
    role: covariate
    variables: [ROKEN, DIABETES, BLOEDDRUK_MEDICATIE]

  - name: L2
    label: Cardiovascular risk factors
    role: covariate
    variables: [SYS_BP, DIAS_BP, VASCULAR RISK SCORE, CHOLESTEROL_LDL]

  - name: L4
    label: Potential disease process markers
    role: covariate
    variables: [PTAU181, NFL, GFAP, AB40, AB42, CEREBRAL BLOOD FLOW]

  - name: L5
    label: Imaging markers of neurovascular damage
    role: covariate
    variables:
      - SMALL VESSEL DISEASE SCORE
      - HIPPOCAMPUS/INTRACRANIAL VOLUME
      - BRAIN/INTRACRANIAL VOLUME

  - name: L6
    label: Current and previous cardiovascular diagnoses / vascular interventions
    role: covariate
    variables:
      - PATIENT GROUP
      - ATHEROSCLEROTIC CARDIOVASCULAR DISEASE HISTORY
      - STROKE HISTORY

  - name: L7
    label: Functional status
    role: covariate
    variables: [MINI MENTAL STATE EXAMINATION, STARKSTEIN SCORE, BASELINE CDR]

  - name: L8
    label: Outcomes
    role: outcome
    variables: [OUTCOME_CDR_INCREASE, OUTCOME_MACE]

  - name: L9
    label: Dropout
    role: selection
    variables: [DROPOUT REASON]

edges:
  layer_ordering: forward
  within_layer: allow
  between_outcomes: forbid
  selection_parents:
    from_roles: [outcome]
    required: true          # forces OUTCOME_* -> DROPOUT REASON into the whitelist
  forbidden: []
  required: []
  max_indegree: 5

discretisation:
  default: {method: quantile, n_bins: 4, threshold: 10}
  per_variable:
    AGE:                          {method: quantile, n_bins: 4}
    VASCULAR RISK SCORE:          {method: edges, edges: [0, 5, 10, 100],
                                   labels: [Low, Moderate, High]}
    SMALL VESSEL DISEASE SCORE:   {method: none}     # 0-4, already discrete
    BASELINE CDR:                 {method: none}
    PTAU181:                      {method: quantile, n_bins: 3}
  freeze_across_bootstrap: true
  never_discretise: [SEX, PATIENT GROUP, STROKE HISTORY, DROPOUT REASON,
                     OUTCOME_CDR_INCREASE, OUTCOME_MACE]

missing:
  impute: iterative_mode
  seed: 1234
  never_impute_roles: [outcome, selection]
  on_missing_outcome: error       # outcomes carry an explicit "Unobserved" state

model:
  algorithm: tabu
  score: K2
  smoothing: auto
  seed: 42
  bootstrap: {n: 200, seed: 42}

variants:
  - name: joint                    # manuscript main analysis
    exclude_layers: [L4]
    outcomes: [OUTCOME_CDR_INCREASE, OUTCOME_MACE]
  - name: cdr_only
    exclude_layers: [L4]
    outcomes: [OUTCOME_CDR_INCREASE]
  - name: mace_only
    exclude_layers: [L4]
    outcomes: [OUTCOME_MACE]
  - name: with_biomarkers          # L4 ablation, manuscript §7
    exclude_layers: []
    outcomes: [OUTCOME_CDR_INCREASE, OUTCOME_MACE]

analyses:
  information:
    targets: [OUTCOME_CDR_INCREASE, OUTCOME_MACE]
    conditional: true
  scenarios:
    bootstrap: 200
    targets: [OUTCOME_CDR_INCREASE, OUTCOME_MACE]
    profiles:
      Healthy profile:
        PATIENT GROUP: Reference
        SMALL VESSEL DISEASE SCORE: "0"
        AGE: 58
        MINI MENTAL STATE EXAMINATION: 29
        BASELINE CDR: "0"
        SEX: Male
      Ill profile:
        PATIENT GROUP: Vascular cognitive impairment
        SMALL VESSEL DISEASE SCORE: "2"
        AGE: 76
        BASELINE CDR: "0"
        SEX: Female
  knob_sweep:
    knob: SMALL VESSEL DISEASE SCORE
    base_profile: {SEX: Female, AGE: 72}    # upstream only — mediators left free
    targets: [OUTCOME_CDR_INCREASE, OUTCOME_MACE]
    bootstrap: 200
    on_mediator: warn

output:
  dir: outputs/
  figures:
    formats: [pdf, png]
    node_color_by: layer
    arc_width: mutual_information
    arc_label: bootstrap_frequency
    cmap_node: coolwarm
    cmap_arc: Blues
    layout: dot
    rankdir: TB
  tables:
    edge_frequencies: true
    information: true
    cpts: [OUTCOME_CDR_INCREASE, OUTCOME_MACE, DROPOUT REASON]
    format: csv
  network:
    formats: [bifxml]
  manifest: true
```

That one file replaces cells 4, 6, 17, 21, 26, 28, 30–35, 39, 42–48, 52–59,
61–62, 66–76, 78–82, 85–96 of `01_bayesian_network.ipynb` — roughly 1,400 of
its 1,945 code lines.

---

## 5. Gap list — what config still cannot express

Ranked by how likely a *new cohort* hits it. 1 = every cohort, always.

| # | Gap | Likelihood | Why config can't do it | Mitigation |
| --- | --- | --- | --- | --- |
| 1 | **Outcome derivation** — turning follow-up columns into `Yes/No/Unobserved`. HBC: ~290 lines with Dutch cause-of-death substring lists, a "moved to nursing home ⇒ CDR increase" rule, and per-timepoint coalescing. | 100% | This is arbitrary computation over an arbitrary schema. Expressing it in YAML means inventing a programming language. | Out of scope. Package starts at an analysis-ready frame. Document the *convention* (explicit `Unobserved` state, `never_impute_roles`) and validate it. |
| 2 | **Censoring / missingness policy beyond the two built-ins.** MICE with `m>1` and pooling, MNAR sensitivity, complete-case, per-column strategies. | 90% | `impute: iterative_mode` is one policy. `m>1` changes the whole downstream API (fit per imputation, pool edge frequencies). | Accept a **list** of frames or an `Imputation` protocol; pool at the bootstrap layer. Scope for v2 — but design the API so it isn't a breaking change. |
| 3 | **Variable renaming / value-label translation.** HBC has `NAME_MAPPING` (22 entries), `LABEL_TRANSLATION` (3 columns), and column-suffix stripping. | 85% | Mostly a flat dict — config *could* do it. | Add optional `data.rename` and `data.value_labels` maps. Cheap, high payoff. Refuse regex-based renaming. |
| 4 | **Derived variables.** `HV_ICV = mean(L_hipp, R_hipp)*100/ICV`, `SYS_BP = mean(sys_a, sys_b)`, SCORE2. | 80% | Needs an expression language. | Two options: (i) `data.derive: {HV_ICV: "..."}` evaluated by `df.eval` — safe for arithmetic, useless for SCORE2; (ii) declare it out of scope. **Recommend (ii)**, with `register_*` plugins as the escape hatch. |
| 5 | **Within-layer arcs.** Current code always allows them (`layer_keys[i:]`). Some cohorts want a layer to be a flat set of exchangeable measurements. | 60% | Already fixed in §4 (`edges.within_layer`) — listed because it is a silent behaviour today that nobody has chosen. | Covered by the schema. |
| 6 | **Multi-cohort pooling.** This is *literally the METAVCI use case*: learn one network across several cohorts, with cohort as a stratifier or a node, plus per-cohort discretisation harmonisation. | 60% (and ~100% for your own roadmap) | Not expressible at all today, and not a small feature: it changes bootstrap semantics (resample within cohort), discretisation (shared edges), and the layer model (cohort has no causal position). | Design the spec so `data.path` can be a list with a `cohort` column now, even if the implementation lands later. **Decide this before v1.0** — retrofitting it will break the schema. |
| 7 | **Multiple learners / algorithm parameters.** MIIC, `ess` for BDeu, per-node indegree caps, edge-prior weights. | 50% | Partly covered by `model.score_params`. `max_indegree` is currently a Python kwarg with no config path. | Covered by the schema; add a passthrough `model.engine_options` with a loud "unportable" warning. |
| 8 | **Uncertainty beyond nonparametric bootstrap.** Bayesian model averaging over structures, permutation nulls for edge frequency, cross-validated predictive checks. | 40% | Different loops, different outputs. | Leave the door open: `model.bootstrap.method: resample` with room for `bayesian` / `permutation`. |
| 9 | **Time-to-event outcomes.** HBC collapses 4-year follow-up to binary and encodes censoring as an `Unobserved` state. A cohort with real survival data will want hazards. | 35% | A discrete BN cannot represent time-to-event. Not a config gap — an engine gap. | Document explicitly as a limitation. Discretised time as an ordinal node is the honest workaround; say so. |
| 10 | **Latent variables / dynamic (temporal) networks.** Repeated measures across visits. | 25% | pyAgrum supports these; the layered-spec model does not. | Out of scope for v1; note it. |
| 11 | **Cohort-specific figures.** Alluvial flows, dropout composition bars. | 25% | Arbitrary matplotlib. | Analysis repo. |
| 12 | **Survey weights / complex sampling.** | 15% | Neither the learner nor the bootstrap supports weights. | Document as unsupported. |

Gaps 1, 2 and 6 are the ones that determine whether this design survives.
1 and 2 are answered by scoping (the package does not preprocess).
**6 is not answered by scoping and needs a decision now.**

---

## 6. HBC-specific things: drop / move / expose

| Item | Where it is | Recommendation |
| --- | --- | --- |
| `DEFAULT_OUTCOME_LAYER_PATTERNS` / `DEFAULT_DROPOUT_LAYER_PATTERNS` | `bn_utils.py:22-23` | **Drop.** Replace with explicit `role:` in the spec. Substring matching on layer names is a correctness bug, not a convenience. |
| `"DROPOUT" not in var.upper()` heuristic | notebook cell 30; mirrored in `core` via patterns | **Drop.** Same reason. |
| Hardcoded `'L4 – Potential disease process markers'` exclusion | notebook cells 30, 93 | **Expose** as `variants.exclude_layers`. Already a parameter in `core/`; the notebook is the stale copy. |
| Dropout-as-selection-layer + forced outcome→dropout arcs | `bn_utils.py:47-94, 198-207` | **Generalise and keep — this is the scientific contribution.** Modelling non-random dropout as a selection node downstream of the outcomes is the reusable idea. Make it declarative (`edges.selection_parents`) and pass the arcs to the learner as a whitelist rather than adding them post-hoc (see §1 defect 5). |
| `plot_knob_sweep` `Yes/No/Unobserved` palette + `"Yes"`-only annotation | `plotting.py:98,127` | **Expose** as `palette=` / `annotate_state=`. |
| `score2` + `PreprocessConfig.risk_region` | `risk_scores.py`, `config.py:29` | **Move to the HBC analysis repo.** A cardiovascular risk equation inside a BN package invites the wrong review questions. |
| `build_grouped_table` / Table 1 | `tables.py` (all 165 lines) | **Move to the HBC repo.** Not a BN concern, unused, and already drifted from the notebook it generalises. |
| `read_sav` / `apply_value_labels` | `io.py` | **Move**, or make an `[spss]` extra. Don't carry `pyreadstat` in the core dependency set. |
| Dutch label dicts, dropout canonicalisation, MACE cause-of-death substrings, `NAME_MAPPING`, `EXTRA_LAYER_ROWS`, `BASELINE_CDR_CATEGORIES`, `enforce_domain_categories` | `preprocess_data.py`, `00_preprocess.ipynb` | **Move to the HBC repo** as `hbc/preprocess.py`. Not generalisable; not worth trying. |
| Alluvial + dropout-composition figures (~330 lines) | `01_bayesian_network.ipynb` cells 9–14 | **Move to the HBC repo.** Reconsider for the package only if a second cohort asks. |
| Biomarker logistic regression (statsmodels) | cell 64 | **Move to the HBC repo.** Different method. Also drops `statsmodels` from the dependency tree. |
| The L4 ablation *workflow* (fit with and without a layer, compare) | cells 61–82 | **Expose** as `variants:` + a `compare_variants()` report. This pattern generalises well and is worth a first-class feature. |
| The `Unobserved` outcome-state convention | `preprocess_data.py:578-584` | **Expose as a validated convention**, not code: `missing.never_impute_roles` + a `validate()` check that outcome columns contain no NaN. This is the single most valuable transferable idea in the repo after the selection layer. |
| `config/global.yml`, `config/global.dcf` | `config/` | **Drop.** R `ProjectTemplate` config for a repo with no R. |
| `preprocess_data.py` | `projects/HBC/` | **Drop after reconciling** with `00_preprocess.ipynb` (§2) — it cannot reproduce the analysis inputs. |

---

## 7. How much of `core/` is machinery vs. judgement

### By lines

| Category | Lines | Share |
| --- | --- | --- |
| Reusable BN machinery (bn_utils minus leaks, discretisation, inference, generic plotting) | ~800 | 55% |
| General, but belongs in *another* package (risk_scores 191, tables 165, io 58, config 108) | ~520 | 35% |
| HBC leaked into `core/` (pattern defaults, palette, `risk_region`, layer-name semantics) | ~50 | 3% |
| Dead (`apply_overrides`, `contains_any`, all of `tables.py` by usage) | ~100 | 7% |

But `core/` is not the analysis. The analysis is 3,200+ unique lines in
`projects/HBC/` (1,945 in the BN notebook, ~1,300 unique preprocessing after
accounting for the script/notebook duplication). Against that denominator:

**reusable machinery ≈ 800 / 4,000 ≈ 20% of the total code that produced the
HBC paper.** The other 80% is cohort-specific — and about half of *that* is
duplication that will disappear when the notebooks are consolidated, so the
honest steady-state figure is roughly **30% machinery, 70% cohort work**.

### By decision

This is the number that should drive the design. Every scientifically
consequential choice in the HBC analysis:

| Decision | Lines | Expressible in YAML? |
| --- | --- | --- |
| Layer assignment (9 layers, ~25 variables) | ~40 (codebook + `EXTRA_LAYER_ROWS`) | **Yes** — it is a mapping. Months of expert work, trivially serialisable. |
| Layer *ordering* (the causal assumption) | 1 list | **Yes.** |
| Which layer to exclude (L4) | 1 string | **Yes** (`variants`). |
| Discretisation: quantile, 4 bins, threshold 10 | 1 call | **Yes** — and this one line silently determines every bin edge in the paper. It deserves to be in a versioned spec far more than in a notebook cell. |
| Edge policy: forward-only, no outcome↔outcome, dropout parents = outcomes only | ~45 | **Yes** (§4 `edges`). |
| Score, algorithm, indegree, seed, bootstrap n | ~10 | **Yes.** |
| Scenario profiles and knob | ~20 | **Yes.** |
| **Outcome derivation** (what counts as MACE; CDR increase; nursing home ⇒ increase) | ~290 | **No.** |
| **Dropout canonicalisation** (Dutch free text → 6 categories) | ~75 | **No.** |
| **The `Unobserved` encoding** (which cases are censored) | ~10 | **No** — but the *rule* it enforces is checkable. |
| **Derived variables** (HV/ICV, SYS_BP, SCORE2) | ~90 | **No** (see §5 gap 4). |

So: **the judgement splits cleanly along the preprocess/model boundary.**
Everything downstream of an analysis-ready dataframe is config-expressible;
everything upstream is not, and no amount of schema design will change that.

**Verdict: a config-driven package is the right design — for the modelling
half only.** Do not let the spec grow a `preprocess:` section. If it does,
you will have built a worse pandas with YAML syntax, and every cohort will
still write Python anyway (only now it will be Python that fights the
framework). Say this explicitly in the package README: *"vcibayes takes a
tidy, analysis-ready dataframe. Getting your cohort to that point is your
code, in your repo."*

One consequence worth stating plainly: with this scoping, the citable package
is small — maybe 900–1,200 lines including the spec loader, validator, CLI
and manifest. That is fine. A small, tested, documented package that does one
thing is more citable than a large one that does everything badly. But it
does mean the package alone is not the paper's methods section — the HBC
analysis repo will still contain most of the actual work, and both need
DOIs.

---

## 8. pyAgrum dependence, and an R entry point

### What is actually pyAgrum-bound

By lines, ~690 of 1,467 (47%) sit in modules that import pyAgrum. By *API
surface*, the dependency is roughly twenty calls:

```
gum.BNLearner(df, template) · useScoreK2/BIC/BDeu · useSmoothingPrior
useLocalSearchWithTabuList · useGreedyHillClimbing · addForbiddenArc
setMaxIndegree · learnBN
DiscreteTypeProcessor.discretizedTemplate
gum.LazyPropagation · setEvidence · posterior
gum.InformationTheory · mutualInformationXY · mutualInformationXYgivenZ
bn.arcs/names/variable/idFromName/parents/children/addArc/existsArc/cpt
gum.saveBN · pyagrum.lib.notebook · pyagrum.lib.image
```

Everything else in those 690 lines is plain pandas/numpy orchestration:
expanding the layer map into ~600 forbidden-arc calls, the bootstrap loop,
resolving `AGE=72` to a bin, the descendant/mediator check, quantile
summarisation, DataFrame assembly. **That orchestration is ~85% of the code
and is engine-agnostic.**

### The uncomfortable part: R already has the machinery

| VCI-Bayes piece | R equivalent |
| --- | --- |
| `configure_guided_structure` (layer → forbidden arcs) | `bnlearn::tiers2blacklist()` |
| `build_bn` (tabu/greedy + score + blacklist + max indegree) | `bnlearn::tabu()` / `hc()` with `blacklist=`, `whitelist=`, `maxp=`, `score = "k2"|"bic"|"bde"` |
| `bootstrap_edge_frequencies` | `bnlearn::boot.strength()` — and it also returns arc *direction* probability, which the pyAgrum path does not compute |
| `LazyPropagation` posteriors | `gRain` (`querygrain`) or `bnlearn::cpquery` |
| `make_type_processor` (quantile binning) | `bnlearn::discretize(method = "quantile")` / `arules::discretize` |
| MI / conditional MI | `bnlearn::` CI tests, `infotheo::mutinformation()` |
| Network rendering | `Rgraphviz`, `bnlearn::graphviz.plot` |

An R user who wanted to reproduce the HBC analysis would write roughly
**200–300 lines of R**, not a reimplementation of `core/`. Two implications:

1. **Do not sell the package on its machinery.** Sell it on the *spec* (a
   declarative, versioned description of a layered BN with an explicit
   selection layer), the *dropout/censoring convention*, and the
   *reproducibility manifest*. Those are what is missing from both ecosystems.
2. **Version the YAML schema as the primary artefact.** Publish it with a
   JSON Schema and a conformance suite: N specs + synthetic datasets +
   expected arc sets and edge frequencies within tolerance. Then an R
   implementation is *verifiable*, and the citation stays on the spec
   regardless of which engine someone runs.

### Feasibility and cost of an R-facing entry point

**Option A — `reticulate` wrapper.** ~150 lines of R + roxygen.
*Cost: 2–3 days to write; high ongoing support.* You inherit every Python
environment problem (pyAgrum wheels, virtualenv discovery, `reticulate`
binding failures on managed research laptops, especially Windows), and R
users get pandas objects they must convert anyway. **Not recommended.**

**Option B — CLI + file boundary. Recommended.**
`vci-bayes run spec.yml --data df.parquet --out outputs/` writes
`bn.bifxml`, `edges.csv`, `information.csv`, `scenarios.csv`, figures, and
`manifest.json`. R side:

```r
system2("vci-bayes", c("run", spec, "--data", data, "--out", out))
edges <- arrow::read_parquet(file.path(out, "edges.parquet"))
bn    <- bnlearn::read.bif(file.path(out, "bn.bifxml"))   # or via gRain
```

A thin R package wrapping that is ~100 lines. *Cost: 3–5 days on top of the
CLI you want anyway.* The boundary is inspectable, versionable and
citable; the Python environment is installed once (pipx/conda) rather than
negotiated per R session. **This is the right call.**

**Option C — native R implementation on `bnlearn`.** ~300 lines + tests.
*Cost: 2–3 weeks including the conformance suite.* Best experience for R
users, but a second implementation to keep in sync forever. Only worth it if
R users turn out to be the majority — and the conformance suite from the
recommendation above is what makes it safe to accept as a community
contribution rather than write yourself.

**Prerequisite for any of B or C:** emit explicit numeric bin edges in the
manifest. Today the bin boundaries exist only inside pyAgrum's label strings
(`(48.4928;61.5777[`, visible in `bn_joint.bifxml`) and are recovered by
regex. No other engine can reproduce your discretisation from that without
reimplementing pyAgrum's quantile rule. Fix this first; it is a ~30-line
change with outsized value.

---

## 9. Suggested order of work

1. **Reconcile the three HBC preprocessing implementations** and delete two.
   Establish which one produced the manuscript numbers.
2. **Port HBC's analysis notebook onto `core/`** and diff: arc set, edge
   frequencies, MI rankings, scenario posteriors. Fix the four defects in
   §1. Do not skip this — it is the only validation `core/` will ever get.
   Resolve the post-hoc `addArc` question (§1 defect 5) here.
3. **Freeze the spec schema** (§4), including a decision on multi-cohort
   pooling (§5 gap 6). Publish the JSON Schema.
4. **Extract `vcibayes`** with the §3 API + CLI + manifest + bin edges.
   Move `risk_scores`, `tables`, `io` out. Add tests (a synthetic cohort
   fixture is enough for 80% of the surface) and CI. Tag `v0.1.0`.
5. **Split the analysis repos.** `hbc-bayes` (pins `vcibayes==0.1.0`,
   carries `hbc/preprocess.py`, the spec, the figure code, the manuscript).
   Delete `projects/METAVCI_*` — there is nothing there to migrate; recreate
   them from `vci-bayes init` when someone actually starts the analysis.
6. **Conformance suite + `vcibayes` R wrapper (option B).**
7. Zenodo DOIs for the package and for `hbc-bayes` separately.

Steps 1–2 are prerequisites for everything else and are where the risk is.
Steps 3–4 are mostly mechanical once 2 is clean.
