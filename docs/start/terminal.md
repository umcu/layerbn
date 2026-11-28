# Terminal basics

layerbn has no windows or buttons: you give it short commands in a **terminal** (also called
command line, shell or console). If you have never used one, this page is all you need.

## Open a terminal

=== "macOS"

    Press ++cmd+space++, type **Terminal** and press ++enter++.

=== "Windows"

    Press the ++windows++ key, type **PowerShell** and press ++enter++.
    (The older *Command Prompt* also works, but the examples here are for PowerShell.)

A window opens with a line that ends in `%`, `$` or `>`. That is the **prompt**: the terminal
is waiting for you to type a command and press ++enter++.

## Where am I?

A terminal always "stands" in one folder, the **working folder**. Commands look for files
there and put new files there.

| To | macOS | Windows |
| --- | --- | --- |
| See which folder you are in | `pwd` | `pwd` |
| List what is in it | `ls` | `dir` |
| Go into a folder | `cd my-study` | `cd my-study` |
| Go up one folder | `cd ..` | `cd ..` |
| Go to your Documents | `cd ~/Documents` | `cd $HOME\Documents` |
| Open a file as if you double-clicked it | `open results/report.html` | `start results\report.html` |
| Open the current folder in Finder / Explorer | `open .` | `explorer .` |

!!! tip "Let the computer type the path"

    Type `cd` followed by a space, then **drag the folder** from Finder or Explorer into the
    terminal window. The full path appears. Press ++enter++.

    Also: press ++tab++ while typing a folder or file name and the terminal completes it.

!!! warning "Spaces in folder names"

    A folder like `My analyses` or a OneDrive path such as
    `OneDrive - UMC Utrecht` contains spaces. Put such a path in quotes, or the terminal reads
    it as several words:

    ```bash
    cd "$HOME/Library/CloudStorage/OneDrive-UMCUtrecht/My analyses"
    ```

    (Inside quotes, write `$HOME` for your home folder: `~` only works without quotes.)

    Dragging the folder in (tip above) adds the quotes or escapes for you.

## Commands you will use

| Command | Does |
| --- | --- |
| `layerbn init my-study` | Create a project folder with a worked example |
| `layerbn init my-cohort --blank` | Create an empty project for your own data |
| `cd my-cohort` | Move into the project |
| `layerbn check --figure` | Check your files and data, and draw your layers |
| `layerbn run --fast` | A quick trial run |
| `layerbn run` | The run you report |

Run `check` and `run` **inside the project folder** (after `cd my-cohort`). From elsewhere,
give the folder: `layerbn run my-cohort`.

??? question "I closed the terminal. Where was I?"

    Nothing is lost: everything is in files. Open a new terminal and `cd` to your project folder
    again. If you used a private Python environment (see [Install](install.md)), activate it
    again first.

[Next: install layerbn :material-arrow-right:](install.md){ .md-button .md-button--primary }
