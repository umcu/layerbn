# Several networks

Fit more than one network in one run, to see what changes when you leave out a layer or a
variable. Each network is learned and bootstrapped on its own, and the report compares the
stability of every arc between them.

```yaml
networks:
  - name: all_variables
    description: All variables in the design table.

  - name: without_exposures
    description: The same, without the exposure layer.
    exclude_layers: [Exposures]
    resamples: 50              # optional: its own number of resamples
```

| Key | Meaning |
| --- | --- |
| `name` | Used in file names and in the report. |
| `description` | Shown in the report. |
| `exclude_layers` | Layers left out. The rest keep their order. |
| `exclude_variables` | Single variables left out. |
| `resamples` | Overrides `bootstrap: resamples` for this network. |

Without a `networks` block, one network with all variables is learned. Run a single network
with `layerbn run my-study --network without_exposures`.

!!! question "What does a difference mean?"

    An arc that appears only when a layer is left out may be explained by that layer, for
    example a mediator or a common cause. See [Comparing networks](../results/comparing.md).
