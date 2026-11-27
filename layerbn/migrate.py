"""Convert a version 2 `spec.yml` to the version 3 files.

Version 2 kept everything in one YAML file and gave the roles `outcome` and
`selection` special meaning. Version 3 keeps variables and layers in a table
(`variables.xlsx`) and the analysis settings in `settings.yml`, and treats all
layers alike.

    layerbn migrate spec.yml

writes `settings.yml` and `variables.xlsx` in a new folder next to the old
file and loads them again to check that they are valid. What the conversion
does with the two roles:

* `role: outcome` layers get `arcs_within: no` (version 2 forbade arcs between
  outcomes) and their variables are marked as targets.
* A `role: selection` layer becomes an ordinary last layer. Version 2 allowed
  arcs into it only from outcomes and always added an arc from each outcome.
  The conversion writes this as `forbid` rules (from every other layer) and
  `require` rules (from the outcomes). A required arc is now part of the
  learning, where version 2 added it after learning, so networks can differ
  slightly from earlier results.
* A variant's `outcomes` list becomes `exclude_variables`.

Comments in the old file are not carried over.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


class MigrationError(ValueError):
    """Raised when the old file cannot be converted."""


def _yaml(data: Mapping[str, Any]) -> str:
    return yaml.safe_dump(dict(data), sort_keys=False, allow_unicode=True,
                          default_flow_style=None, width=100)


def convert(raw: Mapping[str, Any]) -> tuple[dict[str, Any], list[list[str]],
                                             list[list[str]], list[str]]:
    """Return `(settings, variable_rows, layer_rows, notes)` for a version 2 spec."""
    if "layers" not in raw or "variants" not in raw:
        raise MigrationError("this does not look like a version 2 spec: it has no "
                             "'layers' and 'variants'.")
    notes: list[str] = []

    layers = raw["layers"]
    outcome_layers = [x["name"] for x in layers if x.get("role") == "outcome"]
    selection_layers = [x["name"] for x in layers if x.get("role") == "selection"]
    outcome_vars = [v for x in layers if x.get("role") == "outcome" for v in x["variables"]]
    selection_vars = [v for x in layers if x.get("role") == "selection"
                      for v in x["variables"]]

    constraints_old = raw.get("constraints") or {}
    outcomes_may_connect = bool(constraints_old.get("arcs_between_outcomes", False))

    labels: dict[str, str] = {}
    for target in ((raw.get("analyses") or {}).get("scenarios") or {}).get("targets", []):
        if isinstance(target, Mapping) and target.get("label"):
            labels[target["variable"]] = target["label"]

    variable_rows = []
    for layer in layers:
        for variable in layer["variables"]:
            variable_rows.append([
                variable, labels.get(variable, ""), layer["name"], "", "", "", "",
                "yes" if variable in outcome_vars else "", ""])
    layer_rows = []
    for layer in layers:
        inner = ""
        if layer["name"] in outcome_layers and not outcomes_may_connect:
            inner = "no"
        layer_rows.append([layer["name"], "", "no", inner, "", ""])

    settings: dict[str, Any] = {"settings_version": 3,
                                "name": raw.get("name", "migrated analysis")}
    if raw.get("description"):
        settings["description"] = str(raw["description"]).strip()
    settings["output_dir"] = "results"
    data_path = (raw.get("data") or {}).get("path")
    settings["data"] = {"file": f"data/{data_path}" if data_path else None,
                        "missing": "error"}
    if data_path:
        notes.append(f"The data file is now set as 'data/{data_path}' relative to "
                     "settings.yml. Version 2 looked for it in the data_dir of config.yml. "
                     "Move the file or change data: file.")

    d = raw.get("discretisation") or {}
    settings["discretisation"] = {"method": d.get("method", "quantile"),
                                  "bins": d.get("n_bins", 4),
                                  "categorical_max_levels": d.get("threshold", 10)}
    m = raw.get("model") or {}
    settings["learning"] = {"score": m.get("score", "K2"),
                            "search": "tabu" if m.get("use_tabu", True) else "greedy",
                            "max_parents": m.get("max_indegree", 5),
                            "seed": m.get("seed", 42)}
    settings["bootstrap"] = {"resamples": (raw.get("bootstrap") or {}).get("n", 200)}

    # constraints
    constraints: dict[str, Any] = {}
    if "within_layers" in constraints_old:
        constraints["within_layers"] = constraints_old["within_layers"]
    forbid = list(constraints_old.get("forbid") or [])
    require = list(constraints_old.get("require") or [])
    if selection_layers:
        sel = selection_layers[0]
        if constraints_old.get("selection_parents", "outcomes") == "outcomes":
            for layer in layers:
                if layer["name"] not in outcome_layers + selection_layers:
                    forbid.append({"from_layer": layer["name"], "to_layer": sel})
        for outcome_layer in outcome_layers:
            require.append({"from_layer": outcome_layer, "to_layer": sel})
        notes.append(
            f"The selection layer {sel!r} is now an ordinary layer. The rules that "
            "version 2 applied to it are written out under constraints (forbid and "
            "require). Review them.")
    if forbid:
        constraints["forbid"] = forbid
    if require:
        constraints["require"] = require
    for key in ("no_parents", "no_children"):
        if constraints_old.get(key):
            constraints[key] = constraints_old[key]
    if constraints:
        settings["constraints"] = constraints

    # variants -> networks
    networks = []
    for variant in raw["variants"]:
        net: dict[str, Any] = {"name": variant["name"]}
        if variant.get("exclude_layers"):
            net["exclude_layers"] = variant["exclude_layers"]
        keep = set(variant.get("outcomes", []))
        dropped = [v for v in outcome_vars + selection_vars if v not in keep]
        if dropped:
            net["exclude_variables"] = dropped
        if variant.get("bootstrap_n"):
            net["resamples"] = variant["bootstrap_n"]
        networks.append(net)
    settings["networks"] = networks

    # analyses
    analyses: dict[str, Any] = {}
    old = raw.get("analyses") or {}
    if (old.get("information") or {}).get("targets"):
        analyses["importance"] = {"targets": old["information"]["targets"]}
    scenarios = old.get("scenarios") or {}
    if scenarios.get("profiles"):
        block: dict[str, Any] = {"groups": scenarios["profiles"]}
        targets = [t["variable"] if isinstance(t, Mapping) else t
                   for t in scenarios.get("targets", [])]
        if targets:
            block["targets"] = targets
        if scenarios.get("bootstrap_n"):
            block["resamples"] = scenarios["bootstrap_n"]
        analyses["profiles"] = block
    sweep = old.get("knob_sweep") or {}
    if sweep.get("knob"):
        block = {"variable": sweep["knob"]}
        if sweep.get("base_profile"):
            block["fixed"] = sweep["base_profile"]
        if sweep.get("outcomes"):
            block["targets"] = sweep["outcomes"]
        if sweep.get("bootstrap_n"):
            block["resamples"] = sweep["bootstrap_n"]
        analyses["sweep"] = block
    if analyses:
        settings["analyses"] = analyses
        notes.append("Version 2 ran the profiles and the sweep on a variant chosen in the "
                     "notebook. They now run on the first network unless you add "
                     "'network:' to them.")
    return settings, variable_rows, layer_rows, notes


def migrate(spec_path: str | Path, out_dir: str | Path | None = None) -> tuple[Path, list[str]]:
    """Write the version 3 files for a version 2 spec. Returns the folder and notes."""
    from layerbn.project import load_project

    spec_path = Path(spec_path)
    if not spec_path.exists():
        raise MigrationError(f"file not found: {spec_path}")
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise MigrationError(f"{spec_path.name} is not a spec file.")

    settings, variable_rows, layer_rows, notes = convert(raw)
    out = Path(out_dir) if out_dir else spec_path.parent / "migrated"
    out.mkdir(parents=True, exist_ok=True)

    (out / "settings.yml").write_text(
        "# Converted from " + spec_path.name + " by layerbn migrate.\n" + _yaml(settings),
        encoding="utf-8")
    _write_workbook(out / "variables.xlsx", variable_rows, layer_rows)

    load_project(out / "settings.yml")     # raises if the result is not valid
    return out, notes


def _write_workbook(path: Path, variable_rows: list[list[str]],
                    layer_rows: list[list[str]]) -> None:
    """The blank workbook with the converted rows filled in."""
    from openpyxl import load_workbook

    from layerbn.workbook import write_design_workbook

    write_design_workbook(path, demo=False)
    workbook = load_workbook(path)
    for row in variable_rows:
        workbook["variables"].append(row)
    for row in layer_rows:
        workbook["layers"].append(row)
    workbook.save(path)
