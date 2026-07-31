"""VCI-Bayes shared helpers.

Import selectively; nothing here has import-time side effects.

    from core.config import load_project_config, PreprocessConfig
    from core.io import read_sav, apply_value_labels
    from core.preprocess import impute_dataframe, coalesce
    from core.risk_scores import score2
    from core.discretisation import make_type_processor, state_for_value
    from core.bn_utils import build_bn, bootstrap_edge_frequencies, bootstrap_knob_sweep
    from core.inference import mutual_information_scores, conditional_mutual_information_scores
    from core.plotting import default_layer_colors, build_node_colors, plot_knob_sweep
    from core.tables import build_grouped_table

The package intentionally has no `from module import *` re-exports so that
users see the fully qualified path in stack traces and IDE go-to-definition.
"""

__version__ = "0.1.0"
