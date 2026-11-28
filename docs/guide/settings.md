# 4 · Choose the settings

`settings.yml` says **how** to analyse. For a first run you change **one line**: the name of
your data file. Everything else has a sensible default, and every setting is explained in
comments inside the file.

## Open the file

`settings.yml` is a plain text file. Open it with:

=== "macOS"

    **TextEdit**: right-click the file, *Open With → TextEdit*. If you see formatting buttons,
    choose *Format → Make Plain Text*. Or use [VS Code](https://code.visualstudio.com/).

=== "Windows"

    **Notepad**: right-click the file, *Open with → Notepad*. Or use
    [VS Code](https://code.visualstudio.com/).

Do not use Word: it adds formatting that breaks the file.

## The one line you must change

Find the `data:` block and write the name of your file, as it is in the `data` folder:

```yaml
data:
  file: data/my_cohort.csv
```

The path is read **relative to the folder of `settings.yml`**, so `data/my_cohort.csv` means
"the file `my_cohort.csv` in the `data` folder next to this file". A full path also works:

```yaml
  file: '/Users/me/Documents/cohort/my_cohort.csv'      # macOS
  file: 'D:\Research\cohort\my_cohort.csv'               # Windows
```

## Lines you probably want to change

```yaml
name: Cognition after stroke                 # the title of the report
description: >
  800 patients from the XYZ cohort, outcome at two years. Shown in the report.

data:
  file: data/my_cohort.csv
  missing: drop_rows          # analyse complete cases only; default `error` stops instead

bootstrap:
  resamples: 200              # 20 to try things out, 200 or more for the results you report
```

Every resample learns the whole network again, so the run time grows with `resamples`.

## Reading and editing the file

The format is called YAML. Four rules are enough:

| Rule | Example |
| --- | --- |
| A setting is a name, a colon, a space and a value | `bins: 4` |
| **Indentation shows what belongs to what**: use spaces, never tabs | `data:` then `  file: ...` two spaces in |
| Everything after `#` is a comment, for you | `bins: 4   # four groups` |
| Put text with special characters in single quotes | `file: 'D:\data\my file.csv'` |

!!! tip "Typing mistakes are caught"

    An unknown or misspelt setting stops the check with a suggestion ("did you mean
    `resamples`?"), so a setting is never silently ignored.

## Everything else

The other blocks are optional:

| Block | What it does | Page |
| --- | --- | --- |
| `discretisation` | Number and kind of groups for continuous variables | [Bins and sample size](../results/bins.md) |
| `learning` | Score, search, maximum number of parents, random seed | [Reference](../reference/settings.md#learning) |
| `constraints` | Forbid or require single arcs | [Rules for arcs](rules.md) |
| `networks` | Several networks, for example without a layer | [Several networks](networks.md) |
| `analyses` | Profiles and a sweep | [Profiles and sweeps](profiles-sweeps.md) |

Without an `analyses` block, the run gives the network, the stability of every arc and the
information about each target. Profiles and the sweep are added when you define them.

[Next: check and run :material-arrow-right:](check-run.md){ .md-button .md-button--primary }
