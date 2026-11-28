# Start here

These pages take you from nothing to a finished report on simulated data, in about fifteen
minutes. You need no programming experience: you type a handful of commands and look at the
result in your browser.

<div class="grid cards" markdown>

-   :material-console:{ .lg } **1 · Terminal basics**

    Never used a terminal? Five commands are all you need: how to open it, where you are,
    and how to move to a folder.

    [Terminal basics](terminal.md)

-   :material-download:{ .lg } **2 · Install**

    Check your Python, install layerbn with one command, and fix the usual problems.

    [Install layerbn](install.md)

-   :material-play-circle-outline:{ .lg } **3 · Your first run**

    Create the worked example, run it, and open the report and the interactive explorer.

    [Run the example](first-run.md)

</div>

After that, [Your own study](../guide/index.md) takes you through the same steps with your
own data.

!!! tip "In a hurry?"

    If you already work in a terminal:

    ```bash
    python -m pip install "https://github.com/umcu/layerbn/archive/refs/heads/main.zip"
    layerbn init my-study && cd my-study
    layerbn run --fast
    open results/report.html        # Windows: start results\report.html
    ```
