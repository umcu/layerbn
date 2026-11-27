# What the network says

Read this before you write up an analysis. Each page in this section takes one part of the
report and says what it means, and what it does not.

## A Bayesian network, briefly

A Bayesian network is a joint probability distribution over your variables, drawn as a graph.
Each variable has a table of probabilities for its states given the states of its parents.
layerbn learns the graph and the tables from the data, under one restriction: **no arc runs
against the layer order**.

<div class="lb-isnot" markdown>
<div markdown>

#### An arc from A to B means

- Given the other variables in the model, B depends on A.
- You assumed A could not be influenced by B.
- The data support the dependence.

</div>
<div markdown>

#### It does not mean

- That A causes B. That also requires the order to be right, no unmeasured common causes,
  adequate measurements and an adequate sample.
- That A is important. Width and stability say how strong and how certain.

</div>
</div>

## The order is yours, the arcs are the data's

- **Between layers**, the direction comes from your order. The data decide only whether the arc
  is there.
- **Inside a layer**, the data decide whether there is an arc, but often not its direction.
  Treat that direction as arbitrary, unless you have a reason from outside the data.
- **A variable in a later layer** can never be a cause of one in an earlier layer. If that is
  wrong for some pair, the result is wrong for that pair, and the data cannot tell you.

## The parts of the report

<div class="grid cards" markdown>

-   [**The network figure**](network-figure.md)

    Bands, arcs, widths, colours and percentages.

-   [**Arc stability**](stability.md)

    How often an arc returns under resampling, and why that is not a p-value.

-   [**Information about a target**](information.md)

    Mutual information, and how a variable is connected to the target.

-   [**Profiles and sweeps**](profiles-sweeps.md)

    Probabilities for groups, and what conditioning does and does not show.

-   [**Bins and sample size**](bins.md)

    Every result depends on the bins. Look at them first.

-   [**Comparing networks**](comparing.md)

    What it means when an arc changes between networks.

</div>
