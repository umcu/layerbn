"""Command line.

    layerbn init my-study           # a new project with a worked example
    layerbn init my-study --blank   # a new project with empty tables
    layerbn check my-study          # check settings, design table and data
    layerbn run my-study            # run everything, write the results folder
    layerbn migrate old/spec.yml    # convert a version 2 spec

`my-study` is the folder, or the settings file in it. `python -m layerbn`
does the same as `layerbn` and works when the install folder is not on PATH.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent / "templates"

_GITIGNORE = """# The data and the results do not belong in version control.
# settings.yml and variables.xlsx do: they describe the analysis.
data/
results/
.ipynb_checkpoints/
"""


def _settings_file(path: Path | None) -> Path:
    """A settings file, given as the file itself or as the folder that holds it."""
    path = Path(path) if path is not None else Path("settings.yml")
    if path.is_dir():
        path = path / "settings.yml"
    return path


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

DOCS_URL = "https://umcu.github.io/layerbn/"


def _init(folder: Path, *, blank: bool, notebook: bool, force: bool) -> int:
    from layerbn.demo import make_demo_cohort
    from layerbn.workbook import write_design_workbook

    targets = ["settings.yml", "variables.xlsx"] + (["analysis.ipynb"] if notebook else [])
    existing = [t for t in targets if (folder / t).exists()]
    if existing and not force:
        print(f"Error: {folder} already contains {existing}. "
              "Use --force to overwrite, or choose another folder.", file=sys.stderr)
        return 1
    folder.mkdir(parents=True, exist_ok=True)

    template = "settings_blank.yml" if blank else "settings.yml"
    shutil.copyfile(TEMPLATE_DIR / template, folder / "settings.yml")
    write_design_workbook(folder / "variables.xlsx", demo=not blank)
    created = ["settings.yml", "variables.xlsx"]

    (folder / "data").mkdir(exist_ok=True)
    if not blank:
        make_demo_cohort(n=800, seed=0).to_csv(folder / "data" / "demo_cohort.csv",
                                               index=False)
    if notebook:
        shutil.copyfile(TEMPLATE_DIR / "analysis.ipynb", folder / "analysis.ipynb")
        created.append("analysis.ipynb")
    if not (folder / ".gitignore").exists():
        (folder / ".gitignore").write_text(_GITIGNORE, encoding="utf-8")

    where = str(folder)
    if " " in where:
        where = f'"{where}"'
    if blank:
        print(f"Created an empty project in {folder}:\n"
              "  settings.yml      how to analyse (open it in a text editor)\n"
              "  variables.xlsx    your variables and their layers (open it in Excel)\n"
              "  data/             put your data file here\n"
              + ("  analysis.ipynb    an optional notebook\n" if notebook else "")
              + "\nNext:\n"
              "  1. Copy your data file into the data folder.\n"
              "  2. In settings.yml, set `data: file:` to it, e.g. data/my_cohort.csv.\n"
              "  3. In variables.xlsx, fill in the sheets 'layers' and 'variables'.\n"
              "     The sheet 'instructions' explains every column.\n"
              f"  4. cd {where}\n"
              "     layerbn check --figure    checks everything and draws your layers\n"
              "     layerbn run --fast        a quick trial run\n"
              "     layerbn run               the run you report\n"
              f"\nStep-by-step guide: {DOCS_URL}guide/")
    else:
        print(f"Created a worked example in {folder}:\n"
              "  settings.yml          how to analyse (open it in a text editor)\n"
              "  variables.xlsx        the variables and their layers (open it in Excel)\n"
              "  data/demo_cohort.csv  simulated data for 800 participants\n"
              + ("  analysis.ipynb        an optional notebook\n" if notebook else "")
              + "\nTry it:\n"
              f"  cd {where}\n"
              "  layerbn run --fast            about 20 seconds\n"
              "Then open results/report.html in your browser.\n"
              f"\nTo use your own data: {DOCS_URL}guide/\n"
              f"or start from empty tables: layerbn init <folder> --blank")
    return 0


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

def _check(settings: Path, data: Path | None, figure: bool) -> int:
    from layerbn.analysis import Analysis, DataError, read_table
    from layerbn.project import ProjectError, load_project

    project = load_project(settings)
    print(project.summary())
    print("\nSettings and design table are valid.")

    try:
        data_path = project.data_path(data)
    except ProjectError as exc:
        print(f"\nData not checked: {exc}")
        data_path = None

    status = 0
    if data_path is not None:
        if not data_path.exists():
            print(f"\nData not checked: {data_path} does not exist.")
        else:
            try:
                study = Analysis(project, read_table(data_path), verbose=False)
            except DataError as exc:
                print(f"\nProblem with the data:\n{exc}")
                status = 1
            else:
                print(f"\nData file {data_path.name}: {study.n} participants, all "
                      f"{len(project.design.variables)} variables found.")
                for note in study.notes:
                    print(f"  note: {note}")

    if figure:
        from layerbn import figures
        out = project.output_path() / "figures"
        written = figures.save_figure(figures.design_figure(project), out / "design",
                                      formats=("png",))
        print(f"\nDrew the layers: {written[0]}")
    else:
        print("\nAdd --figure to draw the layers and check the order.")
    return status


# ---------------------------------------------------------------------------
# run / migrate
# ---------------------------------------------------------------------------

def _run(args: argparse.Namespace) -> int:
    from layerbn.runner import run_project

    run_project(
        _settings_file(args.settings), data=args.data, output=args.output,
        fast=args.fast, fast_resamples=args.fast_resamples,
        networks=args.network or None,
        formats=("png",) if args.no_pdf else ("png", "pdf"))
    return 0


def _migrate(spec: Path, out: Path | None) -> int:
    from layerbn.migrate import migrate

    folder, notes = migrate(spec, out)
    print(f"Wrote {folder / 'settings.yml'} and {folder / 'variables.xlsx'}, "
          "and loaded them again without errors.")
    for note in notes:
        print(f"  note: {note}")
    print("\nOpen variables.xlsx to check the layers, then run "
          f"`layerbn check {folder}`.")
    return 0


# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="layerbn",
        description="Layered Bayesian networks for cohort studies.")
    parser.add_argument("--traceback", action="store_true",
                        help="show the full Python error, for bug reports")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create a project folder")
    init.add_argument("folder", type=Path)
    init.add_argument("--blank", action="store_true",
                      help="empty tables instead of the worked example")
    init.add_argument("--notebook", action="store_true",
                      help="also write a short Jupyter notebook")
    init.add_argument("--force", action="store_true", help="overwrite existing files")

    check = commands.add_parser("check", help="check settings, design table and data")
    check.add_argument("settings", nargs="?", type=Path,
                       help="settings.yml, or the folder that holds it")
    check.add_argument("--data", type=Path, help="data file, instead of data: file:")
    check.add_argument("--figure", action="store_true",
                       help="draw the layers and variables")

    run = commands.add_parser("run", help="run the analysis and write the results")
    run.add_argument("settings", nargs="?", type=Path,
                     help="settings.yml, or the folder that holds it")
    run.add_argument("--data", type=Path, help="data file, instead of data: file:")
    run.add_argument("--output", type=Path, help="results folder, instead of output_dir:")
    run.add_argument("--fast", action="store_true",
                     help="few bootstrap resamples, for a quick trial run")
    run.add_argument("--fast-resamples", type=int, default=20, metavar="N",
                     help="resamples used with --fast (default 20)")
    run.add_argument("--network", action="append", metavar="NAME",
                     help="only this network (can be repeated)")
    run.add_argument("--no-pdf", action="store_true", help="write PNG figures only")

    migrate = commands.add_parser("migrate", help="convert a version 2 spec.yml")
    migrate.add_argument("spec", type=Path)
    migrate.add_argument("--out", type=Path, help="folder for the new files")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    from layerbn.analysis import DataError
    from layerbn.design import DesignError
    from layerbn.migrate import MigrationError
    from layerbn.project import ProjectError
    from layerbn.settings import SettingsError

    known = (SettingsError, DesignError, ProjectError, DataError, MigrationError,
             FileNotFoundError)
    try:
        if args.command == "init":
            return _init(args.folder, blank=args.blank, notebook=args.notebook,
                         force=args.force)
        if args.command == "check":
            return _check(_settings_file(args.settings), args.data, args.figure)
        if args.command == "run":
            return _run(args)
        return _migrate(args.spec, args.out)
    except known as exc:
        if args.traceback:
            raise
        print(f"\nError: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
