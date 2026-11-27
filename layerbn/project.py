"""A project: the settings and the design, with every name resolved.

`load_project("settings.yml")` reads the settings file, finds and reads the
design table it points to, and checks the two against each other: every
variable and layer named in the settings must exist, arc rules must be
consistent with the layer order and with each other, and every network must
contain enough variables to learn from.

    from layerbn.project import load_project
    project = load_project("settings.yml")
    project.design.layer_map          # layers in causal order
    project.forbidden_pairs           # (parent, child) pairs ruled out
    project.network("main").columns   # the variables of one network

Names in the settings may be data column names or labels from the design
table. They are converted to column names here, and everything downstream
works with column names only.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from layerbn._text import did_you_mean
from layerbn.design import Design, DesignError, load_design
from layerbn.settings import ArcRule, Settings, SettingsError, load_settings


class ProjectError(ValueError):
    """Raised when the settings and the design do not agree."""


@dataclass(frozen=True)
class Network:
    """One network to learn: a subset of the design's variables."""

    name: str
    description: str
    columns: tuple[str, ...]                  # in layer order
    layer_map: Mapping[str, tuple[str, ...]]  # only layers that remain
    excluded_layers: tuple[str, ...]
    excluded_variables: tuple[str, ...]
    resamples: int


@dataclass(frozen=True)
class Project:
    """Settings and design, checked against each other."""

    settings: Settings
    design: Design
    base_dir: Path
    forbidden_pairs: frozenset[tuple[str, str]]
    mandatory_pairs: frozenset[tuple[str, str]]
    no_parents: tuple[str, ...]
    no_children: tuple[str, ...]
    networks: tuple[Network, ...]
    importance_targets: tuple[str, ...]
    profile_groups: tuple[tuple[str, Mapping[str, Any]], ...]
    profile_targets: tuple[str, ...]
    profile_network: str
    sweep_variable: str
    sweep_fixed: Mapping[str, Any]
    sweep_targets: tuple[str, ...]
    sweep_network: str

    # -- access --------------------------------------------------------------

    @property
    def name(self) -> str:
        return self.settings.name

    @property
    def network_names(self) -> list[str]:
        return [n.name for n in self.networks]

    def network(self, name: str | None = None) -> Network:
        """A network by name; the first one if no name is given."""
        if name is None:
            return self.networks[0]
        for network in self.networks:
            if network.name == name:
                return network
        raise ProjectError(
            f"{self.settings.source}: there is no network named {name!r}. "
            f"The networks are {self.network_names}.{did_you_mean(name, self.network_names)}")

    def arcs_within(self, layer_name: str) -> bool:
        """Whether arcs between variables of one layer are allowed."""
        layer = self.design.layer(layer_name)
        if layer.arcs_within is not None:
            return layer.arcs_within
        return self.settings.constraints.within_layers

    @property
    def layers_without_inner_arcs(self) -> frozenset[str]:
        return frozenset(layer.name for layer in self.design.layers
                         if not self.arcs_within(layer.name))

    def resamples_for(self, network_name: str) -> int:
        return self.network(network_name).resamples

    def default_targets(self, network: Network) -> tuple[str, ...]:
        """Targets flagged in the design table, or the last layer's variables."""
        flagged = [c for c in self.design.targets if c in network.columns]
        if flagged:
            return tuple(flagged)
        last = list(network.layer_map.values())[-1]
        return tuple(last)

    def with_resamples(self, n: int) -> Project:
        """A copy that uses `n` bootstrap resamples everywhere (for quick trial runs)."""
        settings = replace(
            self.settings, resamples=n,
            profiles=replace(self.settings.profiles, resamples=None),
            sweep=replace(self.settings.sweep, resamples=None))
        networks = tuple(replace(net, resamples=n) for net in self.networks)
        return replace(self, settings=settings, networks=networks)

    def output_path(self, override: str | Path | None = None) -> Path:
        """Where results are written: the override, else `output_dir` in the settings."""
        if override is not None:
            return Path(override).expanduser()
        path = Path(self.settings.output_dir).expanduser()
        return path if path.is_absolute() else self.base_dir / path

    def data_path(self, override: str | Path | None = None) -> Path:
        """Where the data file is: the override, else `data.file` in the settings."""
        if override is not None:
            return Path(override).expanduser()
        if not self.settings.data.file:
            raise ProjectError(
                f"{self.settings.source}: no data file is given. Set `data: file:` "
                "in the settings, or pass the file on the command line "
                "(layerbn run --data path/to/file.csv).")
        path = Path(self.settings.data.file).expanduser()
        return path if path.is_absolute() else (self.base_dir / path)

    def summary(self) -> str:
        """A plain-text description of the design and the settings."""
        s, d = self.settings, self.design
        lines = [
            f"Project      {s.name}",
            f"Variables    {len(d.variables)} in {len(d.layers)} layers",
            "",
            "Layers, in causal order (an arc may only run to the same layer or "
            "to a layer further down):",
        ]
        width = len(str(len(d.layers)))
        for i, layer in enumerate(d.layers, start=1):
            inner = "" if self.arcs_within(layer.name) else "   [no arcs inside this layer]"
            lines.append(f"  {i:>{width}}. {layer.name}{inner}")
            lines.append(f"       {'; '.join(d.label(c) for c in layer.variables)}")
        lines += ["", "Networks"]
        for n in self.networks:
            drop = ""
            if n.excluded_layers or n.excluded_variables:
                parts = list(n.excluded_layers) + [d.label(c) for c in n.excluded_variables]
                drop = f"  (without {', '.join(parts)})"
            lines.append(f"  {n.name}: {len(n.columns)} variables{drop}")
        lines += [
            "",
            f"Binning      {s.discretisation.bins} {s.discretisation.method} bins for "
            f"continuous variables with more than "
            f"{s.discretisation.categorical_max_levels} distinct values",
            f"Learning     score {s.learning.score}, {s.learning.search} search, "
            f"at most {s.learning.max_parents} parents per variable, "
            f"seed {s.learning.seed}",
            f"Bootstrap    {s.resamples} resamples",
        ]
        if self.forbidden_pairs:
            lines.append(f"Forbidden    {len(self.forbidden_pairs)} arcs")
            lines += [f"  {d.label(p)} -> {d.label(c)}"
                      for p, c in sorted(self.forbidden_pairs)]
        if self.mandatory_pairs:
            lines.append(f"Required     {len(self.mandatory_pairs)} arcs")
            lines += [f"  {d.label(p)} -> {d.label(c)}"
                      for p, c in sorted(self.mandatory_pairs)]
        if self.no_parents:
            lines.append("No parents   " + ", ".join(d.label(c) for c in self.no_parents))
        if self.no_children:
            lines.append("No children  " + ", ".join(d.label(c) for c in self.no_children))
        for note in d.warnings:
            lines.append(f"Note         {note}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def find_design_file(settings: Settings, base_dir: Path) -> Path:
    """The design table named in the settings, or `variables.xlsx`/`.csv` beside them."""
    if settings.data.variables_file:
        path = Path(settings.data.variables_file).expanduser()
        return path if path.is_absolute() else base_dir / path
    for name in ("variables.xlsx", "variables.csv"):
        if (base_dir / name).exists():
            return base_dir / name
    raise ProjectError(
        f"{settings.source}: no design table found. Put `variables.xlsx` next to "
        "the settings file, or name the file under `data: variables_file:`.")


def load_project(settings_path: str | Path) -> Project:
    """Read the settings and the design table they point to, and check both."""
    settings_path = Path(settings_path)
    settings = load_settings(settings_path)
    base_dir = settings_path.resolve().parent
    design = load_design(find_design_file(settings, base_dir),
                         column_pattern=settings.data.column_pattern)
    return build_project(settings, design, base_dir)


def build_project(settings: Settings, design: Design,
                  base_dir: str | Path = ".") -> Project:
    """Check the settings against the design and resolve every name."""
    source = settings.source
    where = lambda key: f"{source}: {key}"  # noqa: E731

    def variable(text: str, key: str) -> str:
        return design.resolve_variable(text, where=where(key))

    def layers(text: str, key: str) -> list[str]:
        return design.resolve_layers(text, where=where(key))

    def variables(values, key: str) -> tuple[str, ...]:
        return tuple(variable(v, f"{key}[{i}]") for i, v in enumerate(values))

    c = settings.constraints
    forbidden = _expand_rules(c.forbid, design, source, "constraints.forbid")
    mandatory = _expand_rules(c.require, design, source, "constraints.require")
    no_parents = variables(c.no_parents, "constraints.no_parents")
    no_children = variables(c.no_children, "constraints.no_children")

    networks = tuple(_resolve_network(n, settings, design) for n in settings.networks)
    names = [n.name for n in networks]

    def pick_network(requested: str | None, key: str) -> str:
        if requested is None:
            return names[0]
        if requested not in names:
            raise ProjectError(
                f"{source}: {key}: there is no network named {requested!r}. "
                f"The networks are {names}.{did_you_mean(requested, names)}")
        return requested

    profile_groups = []
    for label, evidence in settings.profiles.groups:
        resolved = {variable(v, f"analyses.profiles.groups.{label}.{v}"): value
                    for v, value in evidence.items()}
        profile_groups.append((label, resolved))

    sweep = settings.sweep
    sweep_fixed = {variable(v, f"analyses.sweep.fixed.{v}"): value
                   for v, value in sweep.fixed.items()}
    sweep_variable = variable(sweep.variable, "analyses.sweep.variable") \
        if sweep.variable else ""
    if sweep_variable and sweep_variable in sweep_fixed:
        raise ProjectError(
            f"{source}: analyses.sweep.fixed.{design.label(sweep_variable)}: the "
            "variable that is moved across its states cannot also be held fixed.")

    project = Project(
        settings=settings, design=design, base_dir=Path(base_dir),
        forbidden_pairs=frozenset(forbidden), mandatory_pairs=frozenset(mandatory),
        no_parents=no_parents, no_children=no_children, networks=networks,
        importance_targets=variables(settings.importance.targets,
                                     "analyses.importance.targets"),
        profile_groups=tuple(profile_groups),
        profile_targets=variables(settings.profiles.targets,
                                  "analyses.profiles.targets"),
        profile_network=pick_network(settings.profiles.network,
                                     "analyses.profiles.network"),
        sweep_variable=sweep_variable, sweep_fixed=sweep_fixed,
        sweep_targets=variables(sweep.targets, "analyses.sweep.targets"),
        sweep_network=pick_network(sweep.network, "analyses.sweep.network"),
    )
    _check_constraints(project)
    return project


def _expand_rules(rules: tuple[ArcRule, ...], design: Design, source: str,
                  key: str) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for i, rule in enumerate(rules):
        here = f"{source}: {key}[{i}]"

        def end(variable: str | None, layer: str | None, field: str,
                here: str = here) -> list[str]:
            if variable is not None:
                return [design.resolve_variable(variable, where=f"{here}.{field}")]
            members: list[str] = []
            for name in design.resolve_layers(layer, where=f"{here}.{field}_layer"):
                members.extend(design.layer(name).variables)
            return members

        tails = end(rule.from_variable, rule.from_layer, "from")
        heads = end(rule.to_variable, rule.to_layer, "to")
        pairs |= {(t, h) for t in tails for h in heads if t != h}
    return pairs


def _resolve_network(definition, settings: Settings, design: Design) -> Network:
    source = settings.source
    excluded_layers: list[str] = []
    for i, text in enumerate(definition.exclude_layers):
        excluded_layers += design.resolve_layers(
            text, where=f"{source}: networks[{definition.name}].exclude_layers[{i}]")
    excluded_variables = [
        design.resolve_variable(
            text, where=f"{source}: networks[{definition.name}].exclude_variables[{i}]")
        for i, text in enumerate(definition.exclude_variables)]

    layer_map: dict[str, tuple[str, ...]] = {}
    for layer in design.layers:
        if layer.name in excluded_layers:
            continue
        members = tuple(c for c in layer.variables if c not in excluded_variables)
        if members:
            layer_map[layer.name] = members
    columns = tuple(c for members in layer_map.values() for c in members)
    if len(columns) < 2:
        raise ProjectError(
            f"{source}: network {definition.name!r} has {len(columns)} variable(s) "
            "after the exclusions. A network needs at least two.")
    return Network(
        name=definition.name, description=definition.description,
        columns=columns, layer_map=layer_map,
        excluded_layers=tuple(dict.fromkeys(excluded_layers)),
        excluded_variables=tuple(dict.fromkeys(excluded_variables)),
        resamples=definition.resamples or settings.resamples,
    )


def _check_constraints(project: Project) -> None:
    """Reject rules that contradict the layer order or each other.

    Rules can only narrow what the layer order allows. A required arc that
    runs against the order is an error: if the arc should be possible, the
    order is what has to change.
    """
    d, source = project.design, project.settings.source
    rules = project.settings.constraints

    for i, rule in enumerate(rules.require):
        key = f"{source}: constraints.require[{i}]"
        pairs = _expand_rules((rule,), d, source, "constraints.require")
        for parent, child in sorted(pairs):
            p_at, c_at = d.layer_index(parent), d.layer_index(child)
            p_layer, c_layer = d.layers[p_at].name, d.layers[c_at].name
            if p_at > c_at:
                raise ProjectError(
                    f"{key}: {d.label(parent)} -> {d.label(child)} runs against the "
                    f"layer order: {d.label(parent)} is in layer {p_at + 1} "
                    f"({p_layer}) and {d.label(child)} is in the earlier layer "
                    f"{c_at + 1} ({c_layer}). Rules can only narrow what the layer "
                    "order allows. If this arc should be possible, move a variable "
                    "or change the order of the layers.")
            if p_at == c_at and not project.arcs_within(p_layer):
                raise ProjectError(
                    f"{key}: {d.label(parent)} -> {d.label(child)} is inside layer "
                    f"{p_layer!r}, which has arcs_within set to no.")
            if (parent, child) in project.forbidden_pairs:
                raise ProjectError(
                    f"{key}: {d.label(parent)} -> {d.label(child)} is both required "
                    "and forbidden. Remove it from one of the two lists.")
            if child in project.no_parents:
                raise ProjectError(
                    f"{key}: {d.label(child)} must have the parent {d.label(parent)} "
                    "but is also listed under no_parents.")
            if parent in project.no_children:
                raise ProjectError(
                    f"{key}: {d.label(parent)} must have the child {d.label(child)} "
                    "but is also listed under no_children.")

    for column in sorted(set(project.no_parents) & set(project.no_children)):
        raise ProjectError(
            f"{source}: constraints: {d.label(column)} is listed under both "
            "no_parents and no_children, so it could not have any arc.")


__all__ = ["Network", "Project", "ProjectError", "build_project", "load_project",
           "find_design_file", "DesignError", "SettingsError"]
