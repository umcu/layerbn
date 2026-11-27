# Changelog

## 3.0.0 - 2026-11-27

A redesign of how an analysis is described and run. Variables and layers are now
free-form, the analysis is described in a table and a short settings file, and one
command produces the figures, tables and a report. **Results from version 2 can change**
in the ways listed under "Changed", so read this before re-running an analysis you have
already reported.

To convert a version 2 `spec.yml`: `layerbn migrate spec.yml`.

### Changed (breaking)

* **No layer has a special meaning any more.** The roles `outcome` and `selection`
  (dropout) are removed, together with the layer name patterns "Outcomes" and "Dropout"
  that the learner used internally. All layers are treated alike.
  * What `outcome` did for arcs between outcomes is now `arcs_within: no` on a layer.
  * Variables of main interest are marked `target`. They are the default for the
    analyses that need a target and are drawn with a heavy outline.
  * Arcs from outcomes into a dropout variable were forced in after learning. This is
    removed. To obtain the same, write `require` and `forbid` rules. A required arc is now
    part of the learning, so networks can differ slightly from version 2. `layerbn migrate`
    writes these rules.
* **Two files instead of three, and a table instead of YAML for the variables.**
  `variables.xlsx` (or CSV) holds variables, layers and time points. `settings.yml` holds the
  analysis settings. `config.yml` is removed: the data file is set in `settings.yml`
  (`data: file:`) or on the command line (`--data`), and results go to `output_dir`.
* **Settings were renamed** to plain language: `variants` is `networks`, `n_bins` is
  `bins`, `threshold` is `categorical_max_levels`, `max_indegree` is `max_parents`,
  `use_tabu` is `search: tabu | greedy`, `bootstrap: n` is `bootstrap: resamples`,
  `analyses: scenarios` is `analyses: profiles`, `knob_sweep` is `sweep`,
  `information` is `importance`. Unknown settings are now an error with a suggestion.
* **A variant no longer lists `outcomes`.** A network is defined by the layers and variables
  it excludes.
* **The notebook is optional.** `layerbn run` replaces it. `layerbn init --notebook` writes
  a short notebook that calls the same functions.
* **The Python interface changed.** `Analysis` is built from a project (`Analysis.from_files`),
  and the functions of `layerbn.bn_utils` take the layer map and the rules as arguments,
  with no outcome or dropout arguments. `layerbn.spec`, `layerbn.config` and
  `layerbn.plotting` are replaced by `layerbn.design`, `layerbn.settings`, `layerbn.project`
  and `layerbn.figures`.
* **Conditional mutual information is removed** from the importance table. Mutual
  information given the parents of the target is exactly zero for every variable that is not
  a descendant of the target (the local Markov property of a Bayesian network), so the
  column carried no information for most variables. The table now gives each variable's
  mutual information with the target and its relation to the target in the learned structure
  (parent, child, co-parent, other) and the number of arcs between them.
* **Missing values are reported by variable** and stop the analysis, unless
  `data: missing: drop_rows` is set to analyse complete cases.
* **The profile and sweep tables have new column names** (`Probability`, `CI 2.5%`, `State`).
  The sweep table is in lower case with `variable_state` and `target_state`.
* `openpyxl` is a new dependency. pyAgrum is limited to `>=2.1,<2.4`. Quantile bin edges differ
  slightly between pyAgrum 2.1 and 2.3 for the same data, so results move with the
  version. The test suite records the edges for both and fails on a version it has not
  seen. Report the versions with your results (they are at the end of the report).

* **A general example.** `layerbn init` now creates a study with characteristics measured at
  baseline and an outcome at follow-up, with general names (`EXPOSURE_A`, `MEASURE_1`,
  `OUTCOME`). The previous example followed cognitive tests over three time points, which
  suggested that the method needs longitudinal data or is meant for one field.

### Added

* **Optional repeated measures.** If the same variables were measured more than once, list
  each variable once and the time points once. A layer marked `repeated` is expanded into one layer per time point, in time order, and the data
  columns are built from `data: column_pattern:` (`{variable}_{time}`). A variable can be
  limited to some time points.
* **`layerbn run`**: one command that reads the files, checks them against the data, learns
  every network, runs the analyses and writes `results/` with `report.html`, figures (PNG
  and PDF), tables (CSV and one Excel file), the networks (`.bifxml`) and a copy of the
  inputs. `--fast` is a quick trial run, marked as such in the report.
* **`layerbn check`**: reads the settings, the variables table and the data without fitting
  anything, and reports problems in plain language. `--figure` draws the layers.
* **`layerbn init --blank`** for empty tables, and a workbook with dropdown lists for layer
  names, yes/no fields and types, and an instructions sheet.
* **`layerbn migrate`** converts a version 2 `spec.yml`.
* **Per-variable binning**: `bins`, `cutpoints` (your own thresholds, for example an
  established cut-off) and `type` (`categorical` or `continuous`) in the variables table.
* **Layers can differ in whether arcs inside them are allowed** (`arcs_within`).
* **Names can be labels.** Variables in `settings.yml` can be written by column name or by
  label, and a layer name stands for a repeated layer at every time point.
* **Several networks in one run**, with a comparison of arc stability between them.
* **Figures drawn in matplotlib**, with no Graphviz needed: the network with layers as bands
  in causal order (repeated measures aligned across time points), every arc labelled with
  its stability, arcs routed around the boxes they pass, arc stability, information
  about each target, profiles, sweep, network comparison, and the bins. PDFs keep text as
  editable text.
* **An interactive explorer for each network** (`networks/<name>_explorer.html`, or
  `study.explore()` in a notebook). The distribution of every variable is drawn inside its
  node. Click states to set evidence and every other distribution updates, with the prior
  kept for comparison. The page also shows each conditional probability table and arc
  stability. It is one HTML file that needs no Python or internet connection. The inference
  runs in the page and is tested against pyAgrum.
* **The report** contains how to read each part, an automatically written methods paragraph,
  the settings, the versions of the software and a checksum of each input file.
* **The bins table has the exact bin edges** next to the readable names.
* **A documentation site** ([umcu.github.io/layerbn](https://umcu.github.io/layerbn/)),
  built with MkDocs Material from `docs/`: a guided first run, the steps for your own study,
  how to read each result, a full reference including the Python API, and the error
  messages. It shows a live example report and explorer, generated from the current code at
  every build. `mkdocs build --strict` runs in CI.
* **The explorer fits the network to the window** on opening, and on a narrow screen puts
  the side panel below the network.
* **New logo**, drawn in code (`docs/assets/build_logo.py`), in a light and a dark version.
* **A larger test suite**: 192 tests covering the variables table, the settings, the layer
  guarantee on learned networks and on every bootstrap resample, recovery of a known
  structure, the figures, the explorer's inference against pyAgrum, the command line from
  `init` to `report.html`, migration, and the notebook.

### Fixed

* **The BDeu score could not be used.** Selecting it raised an error from pyAgrum. It was
  not covered by a test.
* **PDF figures did not keep editable text** because the font setting was read at the wrong
  time.
* **Unquoted `Yes` and `No` in a profile** were read by YAML as true and false and did not
  match categories called `Yes` and `No`. They are matched now.
* **A mistake in capital letters** (`Age` for `AGE`) now gets a suggestion in every message
  that offers one.
* **CSV files with semicolons** (as saved by Excel in several countries) are read.

### Removed

* The Graphviz-based drawing (`layerbn.plotting`), `layerbn.config`, `config.yml`, the
  `outcome` and `selection` roles, and the `selection_parents` and `arcs_between_outcomes`
  settings.

## 2.0.0 - 2026-08-20

Renamed from `vcibayes` to `layerbn`. The method was never specific to vascular cognitive
impairment, and the name said otherwise. Nothing about the analysis changed in the rename.
Fixed mutual information that was silently dropped for some variables, a bootstrap that
learned under a different prior than the reported network, `constraints.forbid` being ignored
for outcome-to-dropout arcs, and a removed pandas function. Added a test suite and continuous
integration. Capped scikit-learn below 1.9, because that release changes the quantile bin
edges.

## 1.2.1 and earlier

Released as `vcibayes`. See the git history.
