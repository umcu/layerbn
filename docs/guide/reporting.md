# 6 · Report

Open `results/report.html`. Every section starts with a short note on how to read it, and
[Reading the results](../results/index.md) explains each part in more depth.

## The methods paragraph

The report writes a methods paragraph from your settings: the number of participants, the
layers, the score and search, the bins, the number of resamples and the seed. Adapt it; do not
paste it unread.

## What to report

- [ ] The **layers and their order**, the reason for the order, and the variables in each.
- [ ] Any arcs you **forbade or required**, and why.
- [ ] The **number of participants**, and how missing values were handled.
- [ ] The **bins**, including any cut points (`tables/bins.csv` has the exact edges).
- [ ] The score, search, maximum number of parents, **number of resamples** and **seed**.
- [ ] **The stability of the arcs you discuss, as numbers**, not only that they were stable.
- [ ] The versions of layerbn and pyAgrum (at the end of the report).
- [ ] That the network describes **associations in the assumed order**, not causal effects.

## Make it reproducible

Everything that determines the result, apart from the data, is in two files. A copy of both
is in `results/inputs/`, with a checksum of the data file.

```
results/inputs/
├── settings.yml
├── variables.xlsx
└── run_info.json     when it ran, the networks, and the name, size and checksum
                      of each input file, including the data
```

The software versions, the seed and every setting are in the *Reproducibility* section at the
end of the report.

Share these with the manuscript, as a supplement or in a repository. With the same data,
anyone can then run the same analysis.

!!! warning "Software versions change bin edges"

    Quantile bin edges can differ slightly between versions of pyAgrum and scikit-learn, and
    every result depends on the bins. That is why the versions are reported, and why layerbn
    limits the versions it accepts.
