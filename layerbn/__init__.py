"""layerbn — layered Bayesian networks for cohort studies.

The analysis is declared in a YAML spec, not in code. To start a project:

    python -m layerbn init my-study   # writes spec.yml, config.yml, notebook
    python -m layerbn check spec.yml  # validates a spec, runs nothing

Most users need only `Analysis`, which reads every setting from the spec:

    from layerbn.analysis import Analysis
    study = Analysis.from_files("spec.yml", "cohort.parquet")
    study.network("joint")
    study.stable_edges("joint")

The individual functions are available for scripting. They take the layer
map, the score, the seed and the layer role patterns as separate arguments,
so a caller using them directly is responsible for keeping those consistent
with the spec:

    from layerbn.spec import load_spec, check_against_dataframe
    from layerbn.config import load_project_config, PreprocessConfig
    from layerbn.preprocess import impute_dataframe, coalesce
    from layerbn.discretisation import make_type_processor, state_for_value
    from layerbn.bn_utils import build_bn, bootstrap_edge_frequencies, bootstrap_knob_sweep
    from layerbn.inference import mutual_information_scores, conditional_mutual_information_scores
    from layerbn.plotting import default_layer_colors, build_node_colors, plot_knob_sweep

Nothing here has import-time side effects, and pyAgrum is imported inside
functions rather than at module level. The package deliberately provides no
`from module import *` re-exports, so that stack traces and go-to-definition
show the fully qualified path.

Scope: this package starts at an analysis-ready dataframe. Cohort-specific
preprocessing, including outcome derivation, censoring and imputation, lives
in the analysis repository.
"""

__version__ = "2.0.0"
