# 5 · Check and run

Do this in the terminal, **inside your project folder**:

```bash
cd ~/Documents/my-cohort          # Windows: cd $HOME\Documents\my-cohort
```

## Check

```bash
layerbn check --figure
```

This reads `settings.yml`, `variables.xlsx` and your data **without fitting anything**, and
reports in plain language what does not match, and what to change. When everything is right
it looks like this:

```text
Project      Cognition after stroke
Variables    16 in 5 layers

Layers, in causal order (an arc may only run to the same layer or to a layer further down):
  1. Background
       Age (years); Sex; Education
  2. Lifestyle
       Smoking; Alcohol
  ...
Settings and design table are valid.

Data file my_cohort.csv: 812 participants, all 16 variables found.
```

If there is a problem, the message says where:

```text
Error: variables.xlsx, sheet 'variables': variable 'SBP' is in layer 'Clinicals', which is
not on the 'layers' sheet. Did you mean 'Clinical'?
```

Fix it, save, and run `layerbn check --figure` again. Repeat until it says the files are valid.
The [error messages page](../help/troubleshooting.md) explains each message.

With `--figure` it also draws your layers to `results/figures/design.png`:

<figure markdown>
![The design figure](../assets/example-design.png)
<figcaption>Arcs will run from the top down, from a layer to the same layer or a lower one. If a
variable is in the wrong place, change its layer or the order of the layers, and check
again.</figcaption>
</figure>

## Run

=== "1 · A trial"

    ```bash
    layerbn run --fast
    ```

    20 resamples, to see that everything works and to look at the results. The report marks
    itself as a trial run: do not report its numbers.

=== "2 · The run you report"

    ```bash
    layerbn run
    ```

    The number of resamples in `settings.yml`. It prints its progress and an estimate of the
    time left. With 200 resamples and 20 variables, expect several minutes to half an hour.

When it is done, open the report:

=== "macOS"

    ```bash
    open results/report.html
    ```

=== "Windows"

    ```powershell
    start results\report.html
    ```

## What is in `results/`

```
results/
├── report.html        everything, in reading order: open this first
├── figures/           every figure as PNG (slides) and PDF (papers, editable text)
├── tables/            every table as CSV, and all of them in tables.xlsx
├── networks/          each network as .bifxml, and the interactive explorer (.html)
└── inputs/            a copy of settings.yml and variables.xlsx, and a record of the data file
```

!!! warning "A new run overwrites `results/`"

    To keep a result, copy or rename the folder first, or run with another output folder:
    `layerbn run --output results_2026-12-01`.

??? question "It takes too long"

    The time is almost all bootstrap, and grows with the number of resamples. Use `--fast`
    while setting up. `learning: search: greedy` is faster and searches less thoroughly. Fewer
    variables, groups and parents also help.

??? question "Can I use another data file without editing settings.yml?"

    Yes: `layerbn run --data path/to/other_file.csv`. This also keeps the data out of a file
    you might share.

[Next: report :material-arrow-right:](reporting.md){ .md-button .md-button--primary }
