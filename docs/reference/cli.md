# Commands

`my-study` is the project folder or the settings file in it. Without an argument, `check` and
`run` use `settings.yml` in the current folder.

| Command | Does |
| --- | --- |
| `layerbn init FOLDER` | Create a project with a worked example. `--blank`: empty tables. `--notebook`: add a notebook. `--force`: overwrite existing files. |
| `layerbn check [PROJECT]` | Check settings, variables table and data without fitting anything. `--figure`: draw the layers. `--data FILE`: use another data file. |
| `layerbn run [PROJECT]` | Run all analyses and write the results folder. |
| `layerbn migrate SPEC` | Convert a version 2 `spec.yml` to `settings.yml` and `variables.xlsx` in a new folder `migrated` (or `--out FOLDER`). |

Options of `run`:

| Option | Meaning |
| --- | --- |
| `--fast` | Use few bootstrap resamples (default 20, set with `--fast-resamples N`) for a trial run. The report is marked as a trial. |
| `--data FILE` | Data file, instead of `data: file:`. |
| `--output FOLDER` | Results folder, instead of `output_dir:`. |
| `--network NAME` | Run only this network. Can be given more than once. |
| `--no-pdf` | Write PNG figures only. |

`layerbn --traceback ...` shows the full Python error instead of a short message, for bug
reports.
