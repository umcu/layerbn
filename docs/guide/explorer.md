# The interactive explorer

Every run writes each network as an interactive page next to the report:
`results/networks/<name>_explorer.html`. It is **one file** that opens in any browser without
Python or an internet connection, so you can send it to co-authors.

[:material-fullscreen: Open full screen](../generated/example-explorer.html){ .md-button target="_blank" }

<iframe class="lb-embed" src="../../generated/example-explorer.html" title="Interactive network explorer" loading="lazy"></iframe>

| Do | To |
| --- | --- |
| Click a state | Enter it as evidence. Every other distribution updates to its posterior; the grey tick is the prior. |
| ++shift++ + click a second state | "One of these states", for example either of two age bins. |
| Click a variable's name | See its conditional probability table. |
| Clear evidence | Start again. |
| Find variable | Highlight a variable in a large network. |

Arcs are coloured by bootstrap stability, as in the network figure. The inference is exact
(variable elimination on the network's own tables), runs in the page, and is tested against
pyAgrum.

!!! warning "Conditioning, not intervening"

    Clicking a state shows what the network expects for people who *have* that state. It does
    not show what would happen if you *changed* it. The arcs are associations in the order
    you assumed.

From Python, `study.explore("all_variables")` shows the same page inside a notebook. See
[From Python](python.md).
