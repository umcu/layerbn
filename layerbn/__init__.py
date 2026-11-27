"""layerbn: layered Bayesian networks for cohort studies.

Variables are arranged in ordered layers, and the network may only have arcs
from a layer to itself or to a later layer. The analysis is described in two
files, not in code: `variables.xlsx` (variables, layers, time points) and
`settings.yml` (binning, learning, bootstrap, arc rules, follow-up analyses).

From the command line:

    layerbn init my-study       # a new project with a worked example
    layerbn check my-study      # check the files and the data
    layerbn run my-study        # run everything, write results/report.html

From Python:

    from layerbn.analysis import Analysis
    study = Analysis.from_files("settings.yml")
    study.stable_edges()

The modules are `design` (the variables table), `settings`, `project` (both
checked against each other), `analysis`, `figures`, `runner` and `report`.
`bn_utils` and `inference` hold the learning and inference functions and know
nothing about what a variable means.

The package starts at an analysis-ready table. Deriving variables, applying
censoring rules and imputing missing values are decisions about a specific
cohort and are done before this package is used.
"""

__version__ = "3.0.0"
