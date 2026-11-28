# Install

You install layerbn once. It takes about five minutes.

## 1. Check that you have Python

Open a terminal ([how?](terminal.md)) and type:

=== "macOS"

    ```bash
    python3 --version
    ```

=== "Windows"

    ```powershell
    python --version
    ```

You should see `Python 3.11.x` or higher (3.12, 3.13). If so, go to step 2.

??? failure "An error, or an older version"

    Install a current Python from [python.org/downloads](https://www.python.org/downloads/).

    - **Windows**: tick **"Add python.exe to PATH"** at the bottom of the first screen of the
      installer. Without it, the terminal cannot find Python.
    - **macOS**: run the installer, then also double-click *Install Certificates* in the
      Python folder under Applications.

    Then **close the terminal and open a new one**, and check again.

!!! note "`python` or `python3`?"

    On macOS the commands are usually `python3` and `pip3`, on Windows `python` and `pip`. This
    documentation writes `python`; type `python3` on a Mac.

## 2. Install layerbn

```bash
python -m pip install "https://github.com/umcu/layerbn/archive/refs/heads/main.zip"
```

This downloads layerbn and the packages it uses, and takes a minute or two. You do not need
`git` or a GitHub account.

## 3. Check that it works

```bash
layerbn --help
```

You should see a short description and the commands `init`, `check`, `run` and `migrate`.

??? failure "`layerbn: command not found` or `not recognized`"

    layerbn is installed, but the folder pip puts commands in is not on your PATH. Type
    `python -m layerbn` instead of `layerbn` (on a Mac `python3 -m layerbn`), here and
    everywhere in this documentation. It does exactly the same.

??? failure "`error: externally-managed-environment`"

    Your Python (often Homebrew Python on a Mac, or Python on Linux) does not allow installing
    packages into it. Create a private environment for layerbn once:

    === "macOS / Linux"

        ```bash
        python3 -m venv ~/layerbn-env
        source ~/layerbn-env/bin/activate
        python -m pip install "https://github.com/umcu/layerbn/archive/refs/heads/main.zip"
        ```

    === "Windows"

        ```powershell
        python -m venv $HOME\layerbn-env
        $HOME\layerbn-env\Scripts\Activate.ps1
        python -m pip install "https://github.com/umcu/layerbn/archive/refs/heads/main.zip"
        ```

        If PowerShell refuses to run the activation script, run this once and try again:
        `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

    The prompt now starts with `(layerbn-env)`. In every new terminal, run the `activate` line
    again before using layerbn.

??? failure "An error about permissions, a proxy or SSL certificates"

    On a managed (hospital or university) computer, installing may be restricted. Try adding
    `--user` to the install command. If that does not help, ask your IT department to install
    Python packages from PyPI and GitHub, or use the private environment described above.

## Optional extras

Only if you need them:

| You want to | Install |
| --- | --- |
| Read Parquet data files | `python -m pip install pyarrow` |
| Read SPSS (`.sav`) data files | `python -m pip install pyreadstat` |
| Use the optional Jupyter notebook | `python -m pip install jupyterlab` |

CSV, Excel and Stata files work without extras.

## Updating

Run the install command again with `--upgrade`:

```bash
python -m pip install --upgrade "https://github.com/umcu/layerbn/archive/refs/heads/main.zip"
```

!!! info "A fixed version for a paper"

    The command above installs the newest version. To install one released version exactly,
    replace `heads/main` with `tags/` and the version, for example `tags/v3.0.0`. Report the
    version you used; it is printed at the end of every report.

[Next: your first run :material-arrow-right:](first-run.md){ .md-button .md-button--primary }
