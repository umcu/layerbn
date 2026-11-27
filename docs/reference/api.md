# Python API

Generated from the docstrings in the code. For a short introduction, see
[From Python](../guide/python.md).

| Module | Contents |
| --- | --- |
| `layerbn.analysis` | `Analysis`: the whole analysis, from files or from a data frame. |
| `layerbn.figures` | Every figure, and `save_figure`. |
| `layerbn.project` | `load_project`: settings and variables table, checked against each other. |
| `layerbn.design` | `load_design`: the variables table. |
| `layerbn.settings` | `load_settings`: `settings.yml`. |
| `layerbn.runner` | `run_project`: what `layerbn run` calls. |
| `layerbn.explorer` | The interactive explorer. |
| `layerbn.bn_utils` | Structure learning and bootstrap. Knows nothing about what a variable means. |
| `layerbn.inference` | Mutual information and relations to a target. |
| `layerbn.discretisation` | Binning and bin labels. |

## Analysis

::: layerbn.analysis.Analysis
    options:
      heading_level: 3

## Figures

::: layerbn.figures.network_figure
    options:
      heading_level: 3

::: layerbn.figures.design_figure
    options:
      heading_level: 3

::: layerbn.figures.plot_network
    options:
      heading_level: 3

::: layerbn.figures.plot_stability
    options:
      heading_level: 3

::: layerbn.figures.plot_importance
    options:
      heading_level: 3

::: layerbn.figures.plot_profiles
    options:
      heading_level: 3

::: layerbn.figures.plot_sweep
    options:
      heading_level: 3

::: layerbn.figures.plot_comparison
    options:
      heading_level: 3

::: layerbn.figures.save_figure
    options:
      heading_level: 3

## Project files

::: layerbn.project.load_project
    options:
      heading_level: 3

::: layerbn.design.load_design
    options:
      heading_level: 3

::: layerbn.settings.load_settings
    options:
      heading_level: 3

::: layerbn.runner.run_project
    options:
      heading_level: 3

## Explorer

::: layerbn.explorer.write_explorer
    options:
      heading_level: 3

::: layerbn.explorer.explorer_model
    options:
      heading_level: 3

## Learning

::: layerbn.bn_utils.build_bn
    options:
      heading_level: 3

::: layerbn.bn_utils.bootstrap_edge_frequencies
    options:
      heading_level: 3

::: layerbn.bn_utils.configure_structure
    options:
      heading_level: 3

## Inference

::: layerbn.inference
    options:
      heading_level: 3
      show_root_heading: false
