# Install

layerbn runs on Windows, macOS and Linux, from a terminal.

## 1. Python

You need Python 3.11 or newer. Check what you have:

=== "macOS / Linux"

    Open **Terminal** and type:

    ```bash
    python3 --version
    ```

=== "Windows"

    Open **PowerShell** and type:

    ```powershell
    python --version
    ```

If this shows an older version or an error, install a current Python from
[python.org](https://www.python.org/downloads/).

!!! tip "Windows"

    In the Python installer, tick **Add Python to PATH**. Without it, the commands on these
    pages are not found.

## 2. layerbn

```bash
pip install "layerbn @ git+https://github.com/umcu/layerbn@v3.0.0"
```

The quotation marks are needed. Then check that it works:

```bash
layerbn --help
```

??? question "`layerbn: command not found`?"

    The folder where pip puts commands is not on your PATH. Type `python -m layerbn` in place
    of `layerbn`, here and everywhere else in this documentation. It does exactly the same.

## 3. Optional extras

Only install these if you need them.

| You want to | Install |
| --- | --- |
| Read Parquet data files | `pip install pyarrow` |
| Read SPSS (`.sav`) data files | `pip install pyreadstat` |
| Use the optional Jupyter notebook | `pip install "layerbn[notebook] @ git+https://github.com/umcu/layerbn@v3.0.0"` |

CSV, Excel and Stata files work without extras.

[Next: your first run :material-arrow-right:](first-run.md){ .md-button .md-button--primary }
