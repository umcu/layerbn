"""vcibayes — layered Bayesian networks for cohort studies.

Import selectively; nothing here has import-time side effects, and pyAgrum is
imported inside functions rather than at module level.

    from vcibayes.spec import load_spec, check_against_dataframe
    from vcibayes.config import load_project_config, PreprocessConfig
    from vcibayes.preprocess import impute_dataframe, coalesce
    from vcibayes.discretisation import make_type_processor, state_for_value
    from vcibayes.bn_utils import build_bn, bootstrap_edge_frequencies, bootstrap_knob_sweep
    from vcibayes.inference import mutual_information_scores, conditional_mutual_information_scores
    from vcibayes.plotting import default_layer_colors, build_node_colors, plot_knob_sweep

The package intentionally has no `from module import *` re-exports so that
users see the fully qualified path in stack traces and IDE go-to-definition.

Scope: this package starts at an analysis-ready dataframe. Cohort-specific
preprocessing — SPSS reading, risk scores, descriptive tables, outcome
derivation — lives in the analysis repository, not here.
"""

__version__ = "1.0.0"
