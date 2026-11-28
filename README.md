<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-dark.svg">
    <img src="docs/assets/logo.svg" alt="layerbn: layered Bayesian networks for cohort studies" width="520">
  </picture>
</p>

<p align="center">
  <a href="https://doi.org/10.5281/zenodo.22028618"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.22028618.svg" alt="DOI"></a>
  <a href="https://umcu.github.io/layerbn/"><img src="https://img.shields.io/badge/docs-umcu.github.io%2Flayerbn-2166ac" alt="Documentation"></a>
  <a href="https://github.com/umcu/layerbn/actions/workflows/ci.yml"><img src="https://github.com/umcu/layerbn/actions/workflows/ci.yml/badge.svg" alt="tests"></a>
  <img src="https://img.shields.io/badge/python-3.11%E2%80%933.13-blue" alt="Python 3.11 to 3.13">
  <a href="LICENSE"><img src="https://img.shields.io/badge/licence-MIT-green" alt="MIT licence"></a>
</p>

**layerbn** learns a Bayesian network from your cohort data, under an order of the variables
that **you** decide. You place the variables in ordered layers, for example background,
exposures, baseline measures, outcome. An arc may only run within a layer or downwards to a
later layer, never back. The data decide which of the allowed arcs are there, how stable each
one is, and how much each variable tells you about the outcome.

You describe your study in a spreadsheet and a short settings file. You do not write code.

<p align="center">
  <img src="docs/assets/example-network.png" alt="Example network: layers from background to outcome, each variable with its distribution" width="82%">
</p>

<sub>Output on the simulated example. Each row is a layer, from the top down in causal order.
Each card shows how a variable is distributed in the fitted network. Arcs are darker and
wider the more stable and informative they are; the percentage is how often the arc was found
across bootstrap resamples.</sub>

**Full documentation: [umcu.github.io/layerbn](https://umcu.github.io/layerbn/)**

---

## What you need

- [ ] A computer with **Python 3.11 or newer** (Windows, macOS or Linux). Step 1 below checks it.
- [ ] Your data as **one table**: one row per participant, one column per variable, a header
      row, no missing values (or you choose to drop incomplete rows). CSV, Excel, SPSS or
      Stata. See [Prepare your data](#prepare-your-data).
- [ ] An idea of the **order of your variables**: which can influence which. This is the one
      scientific decision layerbn cannot make for you.
- [ ] About 15 minutes to try the example, and an afternoon for your first own analysis.

You do **not** need to know Python. You type a few commands in a terminal and edit two files.

## Quick start: the example in 10 minutes

### 1. Open a terminal and check Python

| macOS | Windows |
| --- | --- |
| Press <kbd>Cmd</kbd>+<kbd>Space</kbd>, type **Terminal**, press Enter. Then type `python3 --version` | Press the Windows key, type **PowerShell**, press Enter. Then type `python --version` |

You should see `Python 3.11` or higher. If you see an error or an older version, install
Python from [python.org/downloads](https://www.python.org/downloads/). On Windows, tick
**"Add python.exe to PATH"** at the start of the installer. Then close and reopen the terminal.

> On macOS the commands are `python3` and `pip3`; on Windows `python` and `pip`. Below we write
> `python`. Use `python3` on a Mac.

### 2. Install layerbn

```bash
python -m pip install "https://github.com/umcu/layerbn/archive/refs/heads/main.zip"
```

This takes a minute. Check it worked:

```bash
layerbn --help
```

If you get `command not found`, type `python -m layerbn` instead of `layerbn`, here and
everywhere else. It does exactly the same.

### 3. Go to the folder where you want to work

The terminal always "stands" in one folder. With `cd` (change directory) you move to another.
Pick a folder for your analyses, for example your Documents folder:

| macOS | Windows |
| --- | --- |
| `cd ~/Documents` | `cd $HOME\Documents` |

**Tip:** type `cd ` (with a space), then drag the folder from Finder or Explorer into the
terminal window and press Enter. The path is filled in for you. If a folder name has spaces,
put the path in quotes: `cd "My analyses"`.

### 4. Create the example project

```bash
layerbn init my-study
```

This makes a new folder `my-study` with everything for one analysis:

```
my-study/
├── settings.yml          HOW to analyse            (open in a text editor)
├── variables.xlsx        WHICH variables, in which layers   (open in Excel)
└── data/
    └── demo_cohort.csv   simulated data, 800 participants
```

### 5. Run it

```bash
cd my-study
layerbn run --fast
```

It prints its progress and takes about 20 seconds. `--fast` uses fewer resamples, which is
fine for trying things out.

### 6. Open the report

The results are in `my-study/results/`. Open the report in your browser:

| macOS | Windows |
| --- | --- |
| `open results/report.html` | `start results\report.html` |

or double-click `report.html` in Finder or Explorer. Everything is in that one file: the
figures, the tables, a note on how to read each, and a methods paragraph. Next to it,
`results/networks/` has an **interactive explorer** of the network that you can click through.

## Your own analysis in 6 steps

Start a new, empty project next to the example:

```bash
cd ..                          # back to the folder above my-study
layerbn init my-cohort --blank
cd my-cohort
```

| Step | What you do | Where |
| --- | --- | --- |
| 1 | **Prepare your data**: one table, checked against the list below. | your own software |
| 2 | **Copy the data file** into the `data` folder of the project. | Finder / Explorer |
| 3 | **Set the file name** in `settings.yml`: `file: data/my_cohort.csv` | text editor |
| 4 | **Fill in `variables.xlsx`**: sheet `layers` (one row per layer, top row first), then sheet `variables` (one row per data column you want to use). The sheet `instructions` explains every column. | Excel |
| 5 | **Check**: `layerbn check --figure`. It reads everything without fitting anything, says in plain language what is wrong and where, and draws your layers to `results/figures/design.png`. Repeat until it says the files are valid. | terminal |
| 6 | **Run**: `layerbn run --fast` for a trial, then `layerbn run` for the results you report. | terminal |

Each step is explained in detail, with examples, in the
[step-by-step guide](https://umcu.github.io/layerbn/guide/).

## Prepare your data

layerbn starts from an analysis-ready table. Check these before step 2:

- **One row per participant, one column per variable,** and the column names in the first row.
  Short names without spaces work best (`AGE`, `SBP`, `MMSE`). Extra columns, such as an ID,
  are allowed and ignored.
- **Missing values are empty cells.** Codes such as `-99`, `999` or `.` are read as real values,
  so change them to empty first. Then either fill them in beforehand (imputation), or set
  `missing: drop_rows` in `settings.yml` to analyse only participants with complete data.
- **Categories as words where you can:** `Female`/`Male`, `No`/`Yes`. Numeric codes work too;
  a number column with at most 10 different values is treated as categories.
- **Continuous variables as numbers**, without units or text (`63.5`, not `63.5 yrs`). They are
  cut into 4 groups of equal size by default; you can choose your own cut-offs.
- **The outcome as one column**, for example `No`/`Yes` for an event during follow-up. Derive it
  yourself first; layerbn does not handle dates or time-to-event.
- **A few hundred participants** for 15 to 20 variables. With fewer, use fewer variables.

Saving from Excel as CSV with semicolons and decimal commas (Dutch or German settings) is fine:
layerbn recognises it. SPSS (`.sav`) files keep their value labels.

## Documentation

| | |
| --- | --- |
| [Install](https://umcu.github.io/layerbn/start/install/) | Python, the terminal, and installing layerbn, for Windows and macOS. |
| [Your own study](https://umcu.github.io/layerbn/guide/) | The 6 steps above in detail: data, layers, the workbook, settings, check and run. |
| [Reading the results](https://umcu.github.io/layerbn/results/) | What each figure and number means, and what it does not. |
| [Reference](https://umcu.github.io/layerbn/reference/) | Every column, setting, command and function. |
| [Error messages](https://umcu.github.io/layerbn/help/troubleshooting/) | What a message means and what to change. |

The network shows associations supported by the data, in the order you assumed. It is not an
estimate of causal effects.

## Common problems

<details>
<summary><code>layerbn: command not found</code> (or "not recognized")</summary>

Use `python -m layerbn` instead of `layerbn` (on macOS `python3 -m layerbn`). The program was
installed, but the folder pip puts commands in is not on your PATH.
</details>

<details>
<summary><code>error: externally-managed-environment</code> when installing</summary>

Your Python (often from Homebrew on macOS) does not allow installing into it directly. Make a
private environment once, and activate it each time you open a terminal:

```bash
python3 -m venv ~/layerbn-env
source ~/layerbn-env/bin/activate          # Windows: $HOME\layerbn-env\Scripts\Activate.ps1
python -m pip install "https://github.com/umcu/layerbn/archive/refs/heads/main.zip"
```
</details>

<details>
<summary><code>data file not found</code></summary>

The path in `data: file:` is read relative to the folder of `settings.yml`. If the file is in
the project's `data` folder, write `file: data/name.csv` with the exact name, including the
extension. Or give the full path.
</details>

<details>
<summary><code>N variable(s) in the design table are not columns of the data file</code></summary>

The `variable` column of `variables.xlsx` must match the column names in your data exactly,
including capitals. The message suggests the closest name it found.
</details>

<details>
<summary><code>The data has missing values</code></summary>

Make the missing cells empty and impute them, or set `missing: drop_rows` in `settings.yml`.
The message lists which variables have how many missing values.
</details>

More in [Error messages](https://umcu.github.io/layerbn/help/troubleshooting/).

## For developers

```bash
git clone https://github.com/umcu/layerbn
cd layerbn
pip install -e ".[dev,notebook,docs]"

pytest                  # the test suite, about a minute
ruff check layerbn tests
mkdocs serve            # the documentation at http://127.0.0.1:8000
```

## Citation and licence

Released under the [MIT licence](LICENSE). Citation metadata is in
[CITATION.cff](CITATION.cff); see [citing layerbn](https://umcu.github.io/layerbn/about/citing/).
Version 1.2.1 and earlier were released as `vcibayes`. The Zenodo concept DOI covers all
versions under both names.

Developed in the [Vascular Cognitive Impairment (VCI) research group](https://research.umcutrecht.nl/research-groups/vascular-cognitive-impairment-vci/)
at UMC Utrecht, department of Neurology and Neurosurgery. This project was led by
[Malin Overmars, PhD](https://research.umcutrecht.nl/researchers/malin-overmars/).
Networks are fitted with [pyAgrum](https://pyagrum.gitlab.io/).
