# The network figure

<figure markdown>
![The network figure](../assets/example-network.png)
</figure>

Read it **from left to right**, and from top to bottom inside a column. No arc points the
other way.

| Mark | Means |
| --- | --- |
| Coloured band | A layer, with its name. Layers are in causal order. |
| Heavy outline | A target variable. |
| Arc **width** | Mutual information between the two variables, in bits, in the fitted network. Square-root scale. The legend gives the largest. |
| Arc **colour**, darker | The arc is found in a larger share of the bootstrap resamples. |
| **Percentage** on an arc | That share, as a number. Each label sits on its own arc and is outlined in the arc's colour. |
| **Dashed** arc | Found in fewer than half of the resamples. |

Arcs that skip a layer are routed through the gaps between boxes, so an arc never hides
behind a variable, and arcs at one box are spread along its side.

## Width and colour answer different questions

<div class="lb-isnot" markdown>
<div markdown>

#### Wide and pale

Much information in the fitted network, but **not stable**: another sample could have given
a different structure.

</div>
<div markdown>

#### Narrow and dark

**Stable**, found in nearly every resample, but it carries little information.

</div>
</div>

Report both. The percentages are in `tables/arcs_<network>.csv`, with the mutual information
of every arc.

!!! tip "Focus on one variable"

    In Python, `figures.network_figure(study, highlight=["OUTCOME"])` fades every arc that
    does not touch the outcome. See [From Python](../guide/python.md).
