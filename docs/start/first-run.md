# Your first run

You will create a project with simulated data, run the analysis, and look at the result. It
takes about ten minutes. Keep the example afterwards: it is the best template for your own
study.

## 1. Go to a folder to work in

Open a terminal and move to the folder where your analyses should live, for example your
Documents folder:

=== "macOS"

    ```bash
    cd ~/Documents
    ```

=== "Windows"

    ```powershell
    cd $HOME\Documents
    ```

Any folder works. A project is just a folder with files in it, so you can move or copy it later.
([More on folders and `cd`](terminal.md))

## 2. Create the example project

```bash
layerbn init my-study
```

The terminal answers:

```text
Created a worked example in my-study:
  settings.yml          how to analyse (open it in a text editor)
  variables.xlsx        the variables and their layers (open it in Excel)
  data/demo_cohort.csv  simulated data for 800 participants

Try it:
  cd my-study
  layerbn run --fast            about 20 seconds
Then open results/report.html in your browser.
```

So you now have:

```
my-study/
├── settings.yml          HOW to analyse
├── variables.xlsx        WHICH variables, in which layers
└── data/
    └── demo_cohort.csv   the data
```

These two files, `settings.yml` and `variables.xlsx`, are all you ever edit. Open them to
have a look; you will fill in your own in [Your own study](../guide/index.md).

## 3. Run it

Move into the project and run:

```bash
cd my-study
layerbn run --fast
```

You see the progress of each step, ending with:

```text
Writing the report

Done. Open .../my-study/results/report.html
```

`--fast` uses 20 bootstrap resamples instead of 100, which is enough to look around. The
report marks itself as a trial run.

## 4. Open the report

=== "macOS"

    ```bash
    open results/report.html
    ```

=== "Windows"

    ```powershell
    start results\report.html
    ```

Or double-click `report.html` in the `results` folder. It opens in your browser and contains,
in reading order, each part with a short note on how to read it:

| Section | Shows |
| --- | --- |
| Design | The layers and variables, before anything was fitted |
| Data and bins | How each continuous variable was cut into groups |
| Network | The learned network, the stability of every arc, and what tells most about the outcome |
| Profiles | The probability of the outcome for groups you defined |
| Sweep | How the outcome changes across one variable |
| Comparison of networks | Arc stability side by side, when you fit more than one network |
| Methods | A paragraph for your methods section, written from your settings |
| Reproducibility | Versions, seed and file checksums |

[Open a full example report](../generated/example-report.html){ .md-button target="_blank" }

## The example study

The data come from the most common design: characteristics measured at baseline, and an
outcome at follow-up. The names are general on purpose; your own variables take their place.

| Layer | Variables | Measured |
| --- | --- | --- |
| Background | `AGE`, `SEX` | baseline |
| Exposures | `EXPOSURE_A` (a score), `EXPOSURE_B` (yes/no) | baseline |
| Baseline measures | `MEASURE_1`, `MEASURE_2`, `MEASURE_3` | baseline |
| Outcome | `OUTCOME` (yes/no), the target | follow-up |

<figure markdown>
![The network of the example](../assets/example-network.png)
<figcaption>The network of the example. Each row is a layer, from the top down. Each card shows
the distribution of a variable in the fitted network. The percentage on an arc is how often
it was found across 100 bootstrap resamples.</figcaption>
</figure>

!!! info "Simulated data"

    The data were generated from a known network, so you can see how well it is recovered.
    They describe no real person and support no scientific claim.

## 5. Click through the network

Next to each network the run writes an interactive page,
`results/networks/all_variables_explorer.html`. Here is the one for this example.
**Click a state**, for example *Yes* under Exposure B, and every other distribution updates.
The grey tick marks the distribution before you clicked.

[:material-fullscreen: Open full screen](../generated/example-explorer.html){ .md-button target="_blank" }

<iframe class="lb-embed" src="../../generated/example-explorer.html" title="Interactive network explorer" loading="lazy"></iframe>

## What next

<div class="grid cards" markdown>

-   **Use your own data**

    Six steps, from preparing your table to the run you report.

    [Your own study :material-arrow-right:](../guide/index.md)

-   **Understand the figures**

    What each figure and number means, and what it does not.

    [Reading the results :material-arrow-right:](../results/index.md)

</div>
