"""Run a whole project and write the results.

    from layerbn.runner import run_project
    result = run_project("settings.yml")
    result.report_path

This is what `layerbn run` does. It reads the settings and the design table,
checks them against the data, learns every network, measures arc stability,
runs the analyses named in the settings, and writes a results folder:

    results/
      report.html          everything below, in reading order
      figures/             PNG and PDF of every figure
      tables/              CSV of every table, and tables.xlsx with all of them
      networks/            each network as .bifxml (can be reopened later)
      inputs/              the settings, design table and data description used
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from layerbn import figures
from layerbn.analysis import Analysis, read_table
from layerbn.project import find_design_file, load_project


@dataclass
class NetworkResult:
    name: str
    description: str
    n_arcs: int
    stability: pd.DataFrame
    importance: pd.DataFrame | None
    figures: dict[str, Path] = field(default_factory=dict)
    figures_importance: dict[str, Path] = field(default_factory=dict)


@dataclass
class RunResult:
    output_dir: Path
    report_path: Path
    started: datetime
    fast: bool
    networks: dict[str, NetworkResult]
    bins: pd.DataFrame
    figures: dict[str, Path]
    profiles: pd.DataFrame | None = None
    sweep: tuple[pd.DataFrame, dict[str, Any]] | None = None
    comparison: pd.DataFrame | None = None
    files: list[Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    inputs: dict[str, dict[str, str]] = field(default_factory=dict)


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(text)).strip("_").lower() or "x"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()[:16]


def run_project(
    settings_path: str | Path,
    *,
    data: str | Path | None = None,
    output: str | Path | None = None,
    fast: bool = False,
    fast_resamples: int = 20,
    networks: list[str] | None = None,
    formats: tuple[str, ...] = ("png", "pdf"),
    verbose: bool = True,
) -> RunResult:
    """Run every analysis in the project and write the results folder."""
    import pyagrum as gum

    from layerbn.report import render_report

    started = datetime.now()
    settings_path = Path(settings_path)
    project = load_project(settings_path)
    if fast:
        project = project.with_resamples(fast_resamples)

    data_path = project.data_path(data)
    df = read_table(data_path)
    study = Analysis(project, df, verbose=verbose)

    names = networks or project.network_names
    for name in names:
        project.network(name)       # raises with a suggestion if misspelt

    out = project.output_path(output)
    for sub in ("figures", "tables", "networks", "inputs"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    def say(message: str) -> None:
        if verbose:
            print(message)

    files: list[Path] = []
    tables: dict[str, pd.DataFrame] = {}
    notes: list[str] = []

    def save_table(name: str, frame: pd.DataFrame) -> None:
        path = out / "tables" / f"{name}.csv"
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        files.append(path)
        tables[name] = frame

    def save_figure(fig: Any, name: str) -> Path:
        import matplotlib.pyplot as plt
        written = figures.save_figure(fig, out / "figures" / name,
                                      formats=tuple(dict.fromkeys(("png", *formats))))
        plt.close(fig)
        files.extend(written)
        return out / "figures" / f"{name}.png"

    # -- inputs ---------------------------------------------------------------
    say(f"\nProject: {project.name}")
    say(f"  {study.n} participants, {len(project.design.variables)} variables, "
        f"{len(project.design.layers)} layers, networks: {names}")
    design_file = find_design_file(project.settings, project.base_dir)
    inputs = {
        "Settings": {"name": settings_path.name, "sha256": _sha(settings_path),
                     "info": f"{settings_path.stat().st_size} bytes"},
        "Design table": {"name": design_file.name, "sha256": _sha(design_file),
                         "info": f"{len(project.design.variables)} variables"},
        "Data": {"name": data_path.name, "sha256": _sha(data_path),
                 "info": f"{study.n_input} rows x {len(df.columns)} columns"},
    }
    for src in (settings_path, design_file):
        shutil.copyfile(src, out / "inputs" / src.name)

    # -- design and bins ---------------------------------------------------------
    say("\nDrawing the design and the bins")
    run_figures: dict[str, Path] = {}
    run_figures["design"] = save_figure(figures.design_figure(project), "design")
    first_network = project.network(names[0])
    bins = study.bins(first_network.name)
    run_figures["bins"] = save_figure(
        figures.plot_bins(study.df, project.design, study.template(first_network.name)),
        "bins")
    save_table("design", project.design.table())
    save_table("bins", bins)

    # -- networks ---------------------------------------------------------------
    results: dict[str, NetworkResult] = {}
    for name in names:
        say(f"\nNetwork '{name}'")
        bn = study.network(name)
        path = out / "networks" / f"{_slug(name)}.bifxml"
        gum.saveBN(bn, str(path))
        files.append(path)

        stability = study.stable_edges(name)
        importance = study.importance(name)
        save_table(f"arcs_{_slug(name)}", stability)
        if len(importance):
            save_table(f"importance_{_slug(name)}", importance)

        result = NetworkResult(
            name=name, description=project.network(name).description,
            n_arcs=len(bn.arcs()), stability=stability,
            importance=importance if len(importance) else None)
        explorer_path = out / "networks" / f"{_slug(name)}_explorer.html"
        study.explore(name, path=explorer_path, stability=True)
        files.append(explorer_path)
        result.figures["network"] = save_figure(
            figures.network_figure(study, name, stability=True), f"network_{_slug(name)}")
        result.figures["stability"] = save_figure(
            figures.plot_stability(
                stability, title=f"Arc stability: {name}",
                subtitle=f"{project.network(name).resamples} bootstrap resamples, "
                         f"{study.n} participants"),
            f"stability_{_slug(name)}")
        for target in (importance["Target"].unique() if len(importance) else []):
            result.figures_importance[target] = save_figure(
                figures.plot_importance(importance, target),
                f"importance_{_slug(name)}_{_slug(target)}")
        results[name] = result

    comparison = None
    if len(names) > 1:
        say("\nComparing networks")
        comparison = study.compare_networks(names)
        save_table("network_comparison", comparison)
        run_figures["comparison"] = save_figure(
            figures.plot_comparison(comparison), "network_comparison")

    # -- follow-up analyses -----------------------------------------------------------
    profiles = None
    if project.profile_groups and project.profile_network in names:
        say(f"\nProfiles (network '{project.profile_network}')")
        try:
            profiles = study.profiles()
            save_table("profiles", profiles)
            run_figures["profiles"] = save_figure(figures.plot_profiles(profiles), "profiles")
        except (ValueError, RuntimeError) as exc:
            notes.append(f"The profile analysis was skipped: {exc}")
            say(f"  skipped: {exc}")

    sweep = None
    if project.sweep_variable and project.sweep_network in names:
        say(f"\nSweep over {study.label(project.sweep_variable)} "
            f"(network '{project.sweep_network}')")
        try:
            sweep = study.sweep()
            save_table("sweep", sweep[0])
            run_figures["sweep"] = save_figure(figures.plot_sweep(*sweep), "sweep")
        except (ValueError, RuntimeError) as exc:
            notes.append(f"The sweep was skipped: {exc}")
            say(f"  skipped: {exc}")

    # -- report -------------------------------------------------------------------------
    say("\nWriting the report")
    result = RunResult(
        output_dir=out, report_path=out / "report.html", started=started, fast=fast,
        networks=results, bins=bins, figures=run_figures, profiles=profiles,
        sweep=sweep, comparison=comparison, files=files, notes=notes, inputs=inputs)
    result.report_path.write_text(render_report(study, result), encoding="utf-8")
    files.append(result.report_path)

    workbook = out / "tables" / "tables.xlsx"
    with pd.ExcelWriter(workbook) as writer:
        for name, frame in tables.items():
            frame.to_excel(writer, sheet_name=name[:31], index=False)
    files.append(workbook)

    info = {"started": started.isoformat(timespec="seconds"), "fast": fast,
            "networks": names, "inputs": inputs, "notes": [*study.notes, *notes]}
    (out / "inputs" / "run_info.json").write_text(json.dumps(info, indent=2),
                                                  encoding="utf-8")
    say(f"\nDone. Open {result.report_path}")
    return result
