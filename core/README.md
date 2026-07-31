# `core/` — shared helpers for VCI-Bayes projects

Reusable building blocks so each subproject (HBC, METAVCI_COGNITION,
METAVCI_WMH_BLOOD, ...) only writes the cohort-specific logic and pulls
the plumbing from here.

## Getting started

```python
# Notebook cell 1: add repo root to sys.path so `import core.*` works
import sys, pathlib
_root = pathlib.Path.cwd()
while _root != _root.parent and not (_root / "core").is_dir():
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.config import load_project_config
from core.io import read_sav, apply_value_labels, read_parquet, write_parquet
from core.preprocess import coalesce, impute_dataframe, normalise_string_categories
from core.discretisation import make_type_processor, state_for_value
from core.bn_utils import build_bn, bootstrap_edge_frequencies, bootstrap_knob_sweep
from core.inference import mutual_information_scores, conditional_mutual_information_scores
from core.plotting import default_layer_colors, build_node_colors, show_and_save_bn, plot_knob_sweep
from core.tables import build_grouped_table, category_rows, Row, format_median_iqr, format_count_pct
```

Once ready to publish as a package (`pip install -e .`), replace the
`sys.path` bootstrap with a real install — the imports don't change.

## Module map

| Module | What it holds |
| --- | --- |
| `config.py` | `PreprocessConfig` dataclass, `load_project_config` YAML loader |
| `io.py` | SPSS reader + label applier, parquet read/write |
| `preprocess.py` | `coalesce`, `to_datetime`, `impute_dataframe`, `normalise_string_categories`, `translate_labels`, `contains_any` |
| `risk_scores.py` | `score2` — 10-year cardiovascular risk (SCORE2 2021) |
| `discretisation.py` | `make_type_processor`, `state_for_value`, `format_bin_label`, `describe_template` |
| `bn_utils.py` | `build_bn` (guided structure learning), `bootstrap_edge_frequencies`, `bootstrap_scenario_risks`, `bootstrap_knob_sweep`, `descendants` |
| `inference.py` | `mutual_information_scores`, `conditional_mutual_information_scores` |
| `plotting.py` | `default_layer_colors`, `build_node_colors`, `show_and_save_bn`, `plot_knob_sweep` |
| `tables.py` | `build_grouped_table` with `Row` / `category_rows` — generalised Table 1 |

## Design notes

- **No cohort constants live here.** Layer names, variable lists, and
  label translations are always passed in as parameters. That is why
  `build_bn` takes `layer_map`, `exclude_layers`, and
  `outcome_patterns` rather than pulling from a global.
- **Nothing runs at import time.** Import is cheap and side-effect free
  (no `pyagrum` config side effects, no logging setup). Notebooks
  configure logging / matplotlib themselves.
- **pyAgrum is imported inside functions**, not at module level. This
  lets you `import core.preprocess` on a machine without pyAgrum, which
  matters for CI and for colleagues who only need the data pipeline.

## Migration status per project

| Project | Uses core/ | Notes |
| --- | --- | --- |
| HBC | No, kept as-is until publication | preprocess_data.py and notebooks unchanged. Post-publication, can migrate — the generic pieces are already ported. |
| METAVCI_COGNITION | Yes | Wired via template in Phase 5. |
| METAVCI_WMH_BLOOD | Yes | Wired via template in Phase 6. |
