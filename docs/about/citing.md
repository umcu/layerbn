# Citing layerbn

If you use layerbn, cite the software. The concept DOI covers every version:

> Overmars M. *layerbn: layered Bayesian networks for cohort studies* (version 3.0.0).
> Zenodo. [doi:10.5281/zenodo.17302710](https://doi.org/10.5281/zenodo.17302710)

Give the version you used. It is printed at the end of every report. Full citation metadata
is in [`CITATION.cff`](https://github.com/umcu/layerbn/blob/main/CITATION.cff), which GitHub
turns into a "Cite this repository" button.

Cite [pyAgrum](https://pyagrum.gitlab.io/) too: it does the learning and the inference.

## In your methods

Every report contains a methods paragraph written from your settings: the number of
participants, the layers, the score and search, the bins, the resamples and the seed. Use it
as a starting point. The checklist in [Report](../guide/reporting.md) lists what a reader
needs in order to judge and reproduce the analysis.
