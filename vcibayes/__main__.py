"""Command line entry point.

Two commands, both aimed at the point before any Python has been written:

    vcibayes init my-study      # create a folder with a spec and a notebook
    vcibayes check spec.yml     # validate a spec without starting a kernel

`check` is worth running whenever the spec changes. Validation is the same
code the notebook runs, so a spec that passes here will load there, and a
typo is reported in a second rather than after a bootstrap has been running
for half an hour.

Both are also available as `python -m vcibayes ...`, which works even when
the install directory is not on PATH.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _init(destination: Path, force: bool) -> int:
    """Copy the spec and notebook templates into a new project folder."""
    files = ["spec.yml", "analysis.ipynb"]
    destination.mkdir(parents=True, exist_ok=True)

    existing = [f for f in files if (destination / f).exists()]
    if existing and not force:
        print(f"error: {destination} already contains {existing}.\n"
              "Pass --force to overwrite, or choose a different folder.",
              file=sys.stderr)
        return 1

    for name in files:
        shutil.copyfile(TEMPLATE_DIR / name, destination / name)
        print(f"  created {destination / name}")

    print(
        f"\nDone. To start:\n"
        f"    cd {destination}\n"
        f"    jupyter lab analysis.ipynb\n\n"
        "The notebook runs as it stands, on a small simulated cohort, so you\n"
        "can see the whole analysis before adapting it. To use your own data,\n"
        "edit spec.yml and set USE_DEMO_DATA = False in the notebook."
    )
    return 0


def _check(path: Path) -> int:
    """Validate a spec and describe what it declares."""
    from vcibayes.spec import SpecError, load_spec

    try:
        spec = load_spec(path)
    except SpecError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    print(f"{path} is valid.\n")
    print(f"  name        {spec.name}")
    print(f"  data        {spec.data_path}")
    print(f"  variables   {len(spec.variables)}")
    print(f"  layers      {len(spec.layers)}, in this order:")
    for i, layer in enumerate(spec.layers):
        role = "" if layer.role == "covariate" else f"  [{layer.role}]"
        print(f"                {i}. {layer.name}{role}")
        print(f"                   {', '.join(layer.variables)}")
    print(f"  variants    {[v.name for v in spec.variants]}")
    print(f"  bootstrap   {spec.bootstrap_n} resamples")

    constraints = spec.constraints
    print("  arcs        only downstream through the layer order above")
    print(f"                within a layer: "
          f"{'allowed' if constraints.within_layers else 'forbidden'}")
    print(f"                between outcomes: "
          f"{'allowed' if constraints.arcs_between_outcomes else 'forbidden'}")
    if spec.layers_with_role("selection"):
        print(f"                into the selection layer: from "
              f"{constraints.selection_parents}")
    for label, pairs in (("forbidden", spec.forbidden_pairs),
                         ("required", spec.mandatory_pairs)):
        if pairs:
            print(f"                {label} ({len(pairs)}):")
            for parent, child in sorted(pairs):
                print(f"                  {parent} -> {child}")
    if constraints.no_parents:
        print(f"                no parents: {list(constraints.no_parents)}")
    if constraints.no_children:
        print(f"                no children: {list(constraints.no_children)}")

    print("\nArcs may only run from a layer to itself or to one below it in "
          "that list.\nIf the order above is not the order you would defend, "
          "reorder `layers` in the spec.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vcibayes",
        description="Layered Bayesian networks for cohort studies.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    init = subcommands.add_parser(
        "init", help="create a project folder with a spec and a notebook")
    init.add_argument("destination", type=Path,
                      help="folder to create the files in")
    init.add_argument("--force", action="store_true",
                      help="overwrite existing files")

    check = subcommands.add_parser(
        "check", help="validate a spec.yml and summarise what it declares")
    check.add_argument("spec", type=Path, help="path to spec.yml")

    args = parser.parse_args(argv)
    if args.command == "init":
        return _init(args.destination, args.force)
    return _check(args.spec)


if __name__ == "__main__":
    raise SystemExit(main())
