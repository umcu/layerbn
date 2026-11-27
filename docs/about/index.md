# About layerbn

layerbn learns Bayesian networks from cohort data under an order of the variables that you
specify. It is general: it suits any study whose variables can be arranged in ordered layers,
with one or more outcomes at the end.

<div class="grid cards" markdown>

-   :material-cogs:{ .lg } [**How it works**](how-it-works.md)

    What happens between `layerbn run` and the report.

-   :material-format-quote-close:{ .lg } [**Citing layerbn**](citing.md)

    The DOI, and what to put in your methods.

-   :material-update:{ .lg } [**Upgrading from version 2**](upgrading.md)

    Convert an old `spec.yml`, and what changes in the results.

-   :material-history:{ .lg } [**Changelog**](changelog.md)

    Every version and what changed.

</div>

## Who made it

layerbn was developed in the
[Vascular Cognitive Impairment (VCI) research group](https://research.umcutrecht.nl/research-groups/vascular-cognitive-impairment-vci/)
at UMC Utrecht, department of Neurology and Neurosurgery, led by
[Malin Overmars, PhD](https://research.umcutrecht.nl/researchers/malin-overmars/). It was first
used in a vascular cognitive impairment cohort, and was released as `vcibayes` up to
version 1.2.1.

Networks are fitted with [pyAgrum](https://pyagrum.gitlab.io/). layerbn is released under the
[MIT licence](https://github.com/umcu/layerbn/blob/main/LICENSE).
