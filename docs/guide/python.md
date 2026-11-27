# From Python

The command line is a thin layer over a Python interface. Use it for a script, a notebook,
or a figure the report does not have.

```python
from layerbn.analysis import Analysis
from layerbn import figures

study = Analysis.from_files("my-study/settings.yml")

study.stable_edges("all_variables")         # arc stability, as a table
study.importance("all_variables")           # mutual information with the targets
study.profiles()                            # the profiles in the settings

fig = figures.network_figure(study, "all_variables", highlight=["OUTCOME"])
figures.save_figure(fig, "my_network")      # my_network.png and my_network.pdf

study.explore("all_variables")              # the explorer, inside a notebook
```

Everything reads from the same two files as `layerbn run`, so a script and the command give
the same result.

## A notebook

```bash
layerbn init my-study --notebook
```

adds a short Jupyter notebook that runs the same steps one at a time. It needs the
`notebook` extra (see [Install](../start/install.md#3-optional-extras)).

Every class and function: [Python API](../reference/api.md).
