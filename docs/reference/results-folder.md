# The results folder

```
results/
  report.html
  figures/    design, bins, network_<name>, stability_<name>,
              importance_<name>_<target>, profiles, sweep, network_comparison  (.png and .pdf)
  tables/     design, bins, arcs_<name>, importance_<name>, profiles, sweep,
              network_comparison  (.csv), and tables.xlsx with all of them
  networks/   <name>.bifxml, <name>_explorer.html
  inputs/     settings.yml, variables.xlsx, run_info.json
```

The `arcs_<name>` table has one row per arc seen in any resample: parent, child, their
layers, the share of resamples that contained the arc (`Frequency`), whether the arc is in
the network learned from all data (`In network`) and the mutual information in bits. The
`bins` table gives both readable names and the exact edges used.

## The explorer

`<name>_explorer.html` is the network as an interactive page. It is one file that opens in
any browser without Python or an internet connection, so it can be sent to co-authors. Every
node shows the distribution of its variable. Click a state to enter it as evidence; hold
Shift (or Ctrl/Cmd) to add a second state of the same variable ("one of these"). All other
distributions update to their posterior, with the prior kept as a tick mark. Click a
variable's name to see its conditional probability table. Arcs are coloured by bootstrap
stability. The inference is exact (variable elimination on the network's own tables) and is
tested against pyAgrum.

See [The interactive explorer](../guide/explorer.md).
