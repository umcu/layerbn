# 4 · Choose the settings

`settings.yml` says **how** to analyse. Open it in a text editor (Notepad, TextEdit, VS
Code). Every setting is explained in comments inside the file, and the defaults are
reasonable. On a first run you change only two things.

## Where the data are

```yaml
data:
  file: data/my_cohort.csv      # relative to settings.yml, or a full path
```

Or leave the path out of the file, so that the data are not named in a file you share, and
give it when you run:

```bash
layerbn run my-study --data "D:\data\cohort.csv"
```

## How many bootstrap resamples

```yaml
bootstrap:
  resamples: 100
```

Each resample learns the whole network again, so the run time grows in proportion.

| Purpose | Resamples |
| --- | --- |
| Setting up, a first look | 20, or `--fast` on the command line |
| Results you report | 200 or more |

## Everything else

The other blocks are optional. Each has its own page:

| Block | What it does | Page |
| --- | --- | --- |
| `discretisation` | Number and kind of bins | [Bins and sample size](../results/bins.md) |
| `learning` | Score, search, maximum number of parents, seed | [Reference](../reference/settings.md#learning) |
| `constraints` | Forbid or require arcs | [Rules for arcs](rules.md) |
| `networks` | Several networks, without a layer or variable | [Several networks](networks.md) |
| `analyses` | Targets, profiles, sweep | [Profiles and sweeps](profiles-sweeps.md) |

!!! tip "Typing mistakes are caught"

    An unknown or misspelt setting is an error with a suggestion, so a setting can never be
    silently ignored.

[Next: check and run :material-arrow-right:](check-run.md){ .md-button .md-button--primary }
