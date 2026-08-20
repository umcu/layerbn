# Changelog

## 2.0.0 — 2026-08-20

Renamed from `vcibayes` to **`layerbn`**. The method was never specific to
vascular cognitive impairment; the name said otherwise, and put off readers
in every other field. Nothing about the analysis changed in the rename.

### Breaking

- **The package is now `layerbn`.** Update imports (`from layerbn.analysis
  import Analysis`) and the command (`python -m layerbn init`). The repository
  moved to `umcu/layer-bn`; GitHub redirects the old URL, and the Zenodo
  concept DOI is unchanged, so existing citations still resolve.
- **`PreprocessConfig` is now `ProjectConfig`**, and `config.yml` needs only
  `project_root`. `raw_dir` is accepted as an alias for the new `data_dir`,
  and `PreprocessConfig` still imports, so existing project code keeps working.
  The cohort-specific `risk_region` key is no longer a field; like any other
  unrecognised key it is preserved in `config.extra`.
- **`scikit-learn` is capped below 1.9**, which changes the default quantile
  method and therefore every bin edge. See "Reproducibility" below.

### Fixed

- **Mutual information was silently dropped for some variables.**
  `mutual_information_scores` and `conditional_mutual_information_scores`
  shared one inference engine across the loop, but `InformationTheory`
  restricts the engine it is given to that query's variables, so later
  variables raised `does not belong to this optimized inference`. The
  exception was swallowed and the variable vanished from the ranking — in
  the demo cohort, `DROPOUT REASON` was reported as blank when its MI with
  `OUTCOME EVENT` is 0.19. Failures are now recorded as `NaN` rather than
  omitted, so a gap is visible instead of invisible. `Analysis.arc_widths`
  had the same shared-engine pattern and could silently render arcs at a
  placeholder width.
- **The bootstrap learned under a different prior than the reported
  network.** `bootstrap_knob_sweep` forced `use_smoothing=True`, which with
  the default K2 score stacks a Laplace prior on top of K2's implicit one.
  aGrUM emitted *"the K2 score already contains a different 'implicit'
  prior ... the learning will probably be biased"* once per fit — several
  hundred lines in a normal notebook run — and the sweep's interval
  described a procedure that produced no reported result. The smoothing
  prior is now applied only for BIC, which is the only supported score
  without a prior of its own.
- **`constraints.forbid` was ignored for outcome→dropout arcs.** Those arcs
  are added after learning so that scenario inference always sees the
  dropout mechanism, and the re-add ran unconditionally — so forbidding one
  had no effect, silently, for exactly the arcs the selection layer exists
  to model. An explicitly forbidden pair is now left out.
- `impute_dataframe` used `pd.api.types.is_categorical_dtype`, removed in
  pandas 3.

### Added

- **A test suite** — 65 tests covering spec validation, the constraint
  solver, the layer guarantees checked on learned networks, discretisation,
  the CLI, `config.yml`, and the template notebook executed end to end.
  There were none before.
- **Continuous integration** on Python 3.11–3.13, Linux and macOS,
  including a check that the built wheel actually contains the templates
  `init` copies out of it.
- `python -m layerbn init` now also writes `config.yml` and a `.gitignore`
  that keeps `config.yml` and `outputs/` out of version control.

### Reproducibility

- `tests/test_reproducibility.py` pins the demo cohort's bin edges. Every
  result this package reports is conditional on the discretisation, and the
  edges come from scikit-learn via pyAgrum — neither of which promises to
  hold them fixed across versions. If an upgrade moves them, the suite now
  fails loudly rather than quietly rewriting your findings.
- `pyagrum` is pinned to `>=2,<3`: the 2.0 release renamed the import and
  moved the learner API, so 1.x cannot run this package.

---

## 1.2.1 and earlier

Released as `vcibayes`. See the git history.
