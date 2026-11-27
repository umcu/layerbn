"""Analysis settings, read from `settings.yml`.

The settings file says *how* the analysis is done: where the data and the
design table are, how continuous variables are binned, how the network is
learned, how many bootstrap resamples are used, which arcs are ruled out or
required, which networks are fitted and which follow-up analyses are run.
It does not say which variables exist or how they are layered. That is the
design table (`layerbn.design`).

Neither file contains a path that only exists on one computer, as long as
the data is kept inside the project folder or passed with `--data`, so both
can be shared with a manuscript.

    from layerbn.settings import load_settings
    settings = load_settings("settings.yml")

Values are checked when the file is read. Every error names the key by its
path in the file, and an unknown key is an error, so a misspelt setting is
reported instead of being ignored.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from layerbn._text import did_you_mean

SETTINGS_VERSION = 3
SCORES = ("K2", "BIC", "BDEU")
SEARCHES = ("tabu", "greedy")
BIN_METHODS = ("quantile", "uniform")
MISSING_POLICIES = ("error", "drop_rows", "category")


class SettingsError(ValueError):
    """Raised for a problem in settings.yml. The message names the key."""


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _fail(source: str, key: str, message: str) -> None:
    raise SettingsError(f"{source}: {key}: {message}")


def _mapping(value: Any, source: str, key: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        _fail(source, key, f"expected a block of 'name: value' lines, got "
                           f"{type(value).__name__}.")
    return value


def _list(value: Any, source: str, key: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(source, key, f"expected a list, got {type(value).__name__}. "
                           "Write a list as [a, b] or as lines starting with '-'.")
    return list(value)


def _text(value: Any, source: str, key: str) -> str:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool) \
            or not str(value).strip():
        _fail(source, key, f"expected text, got {value!r}.")
    return str(value)


def _integer(value: Any, source: str, key: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(source, key, f"expected a whole number, got {value!r}.")
    if minimum is not None and value < minimum:
        _fail(source, key, f"must be at least {minimum}, got {value}.")
    return value


def _boolean(value: Any, source: str, key: str) -> bool:
    if not isinstance(value, bool):
        _fail(source, key, f"expected true or false, got {value!r}.")
    return value


def _choice(value: Any, options: Sequence[str], source: str, key: str,
            *, upper: bool = False) -> str:
    text = _text(value, source, key)
    probe = text.upper() if upper else text.lower()
    if probe not in [o.upper() if upper else o.lower() for o in options]:
        _fail(source, key, f"{text!r} is not allowed. Choose one of "
                           f"{list(options)}.{did_you_mean(text, options)}")
    return probe if upper else text.lower()


def _check_keys(block: Mapping[str, Any], allowed: Sequence[str],
                source: str, where: str) -> None:
    for key in block:
        if key not in allowed:
            prefix = f"{where}.{key}" if where else str(key)
            _fail(source, prefix,
                  f"unknown setting. The settings here are: {', '.join(allowed)}."
                  f"{did_you_mean(str(key), allowed)}")


# ---------------------------------------------------------------------------
# data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DataSettings:
    file: str | None = None
    variables_file: str | None = None
    missing: str = "error"
    column_pattern: str = "{variable}_{time}"


@dataclass(frozen=True)
class Discretisation:
    method: str = "quantile"
    bins: int = 4
    categorical_max_levels: int = 10


@dataclass(frozen=True)
class Learning:
    score: str = "K2"
    search: str = "tabu"
    max_parents: int = 5
    seed: int = 42


@dataclass(frozen=True)
class ArcRule:
    """One arc rule. Each end is a variable or a whole layer, as written."""

    from_variable: str | None = None
    from_layer: str | None = None
    to_variable: str | None = None
    to_layer: str | None = None

    def describe(self) -> str:
        tail = self.from_variable or f"layer {self.from_layer!r}"
        head = self.to_variable or f"layer {self.to_layer!r}"
        return f"{tail} -> {head}"


@dataclass(frozen=True)
class Constraints:
    forbid: tuple[ArcRule, ...] = ()
    require: tuple[ArcRule, ...] = ()
    no_parents: tuple[str, ...] = ()
    no_children: tuple[str, ...] = ()
    within_layers: bool = True


@dataclass(frozen=True)
class NetworkDef:
    name: str
    description: str = ""
    exclude_layers: tuple[str, ...] = ()
    exclude_variables: tuple[str, ...] = ()
    resamples: int | None = None


@dataclass(frozen=True)
class ImportanceSettings:
    targets: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProfileSettings:
    groups: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    targets: tuple[str, ...] = ()
    network: str | None = None
    resamples: int | None = None


@dataclass(frozen=True)
class SweepSettings:
    variable: str = ""
    fixed: Mapping[str, Any] = field(default_factory=dict)
    targets: tuple[str, ...] = ()
    network: str | None = None
    resamples: int | None = None


@dataclass(frozen=True)
class Settings:
    source: str
    name: str
    description: str
    output_dir: str
    data: DataSettings
    discretisation: Discretisation
    learning: Learning
    resamples: int
    constraints: Constraints
    networks: tuple[NetworkDef, ...]
    importance: ImportanceSettings
    profiles: ProfileSettings
    sweep: SweepSettings


# ---------------------------------------------------------------------------
# loader
# ---------------------------------------------------------------------------

_TOP_LEVEL = ("settings_version", "name", "description", "output_dir", "data",
              "discretisation", "learning", "bootstrap", "constraints",
              "networks", "analyses")


def load_settings(path: str | Path) -> Settings:
    """Read and check `settings.yml`. Raises `SettingsError` naming the key."""
    path = Path(path)
    if not path.exists():
        raise SettingsError(f"settings file not found: {path}")
    source = path.name
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SettingsError(f"{source}: the file is not valid YAML. {exc}") from exc
    return parse_settings(raw, source=source, default_name=path.stem)


def parse_settings(raw: Any, *, source: str = "settings.yml",
                   default_name: str = "analysis") -> Settings:
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        _fail(source, "<top level>", "the file must be a block of 'name: value' lines.")

    if "layers" in raw or "spec_version" in raw or "variants" in raw:
        raise SettingsError(
            f"{source}: this is a version 2 spec (it has 'layers', "
            "'variants' or 'spec_version'). Version 3 keeps variables and "
            "layers in a table. Convert the file with\n"
            f"    layerbn migrate {source}")

    _check_keys(raw, _TOP_LEVEL, source, "")
    version = raw.get("settings_version", SETTINGS_VERSION)
    if version != SETTINGS_VERSION:
        _fail(source, "settings_version",
              f"this version of layerbn reads settings_version {SETTINGS_VERSION}, "
              f"the file says {version!r}.")

    return Settings(
        source=source,
        name=_text(raw.get("name", default_name), source, "name"),
        description=str(raw.get("description", "") or "").strip(),
        output_dir=_text(raw.get("output_dir", "results"), source, "output_dir"),
        data=_parse_data(raw, source),
        discretisation=_parse_discretisation(raw, source),
        learning=_parse_learning(raw, source),
        resamples=_parse_bootstrap(raw, source),
        constraints=_parse_constraints(raw, source),
        networks=_parse_networks(raw, source),
        **_parse_analyses(raw, source),
    )


def _parse_data(raw: Mapping[str, Any], source: str) -> DataSettings:
    block = _mapping(raw.get("data"), source, "data")
    _check_keys(block, ("file", "variables_file", "missing", "column_pattern"),
                source, "data")
    pattern = _text(block.get("column_pattern", "{variable}_{time}"),
                    source, "data.column_pattern")
    return DataSettings(
        file=_text(block["file"], source, "data.file") if block.get("file") else None,
        variables_file=(_text(block["variables_file"], source, "data.variables_file")
                        if block.get("variables_file") else None),
        missing=_choice(block.get("missing", "error"), MISSING_POLICIES,
                        source, "data.missing"),
        column_pattern=pattern,
    )


def _parse_discretisation(raw: Mapping[str, Any], source: str) -> Discretisation:
    block = _mapping(raw.get("discretisation"), source, "discretisation")
    _check_keys(block, ("method", "bins", "categorical_max_levels"),
                source, "discretisation")
    return Discretisation(
        method=_choice(block.get("method", "quantile"), BIN_METHODS,
                       source, "discretisation.method"),
        bins=_integer(block.get("bins", 4), source, "discretisation.bins", minimum=2),
        categorical_max_levels=_integer(
            block.get("categorical_max_levels", 10), source,
            "discretisation.categorical_max_levels", minimum=0),
    )


def _parse_learning(raw: Mapping[str, Any], source: str) -> Learning:
    block = _mapping(raw.get("learning"), source, "learning")
    _check_keys(block, ("score", "search", "max_parents", "seed"), source, "learning")
    return Learning(
        score=_choice(block.get("score", "K2"), ("K2", "BIC", "BDeu"),
                      source, "learning.score", upper=True),
        search=_choice(block.get("search", "tabu"), SEARCHES, source, "learning.search"),
        max_parents=_integer(block.get("max_parents", 5), source,
                             "learning.max_parents", minimum=1),
        seed=_integer(block.get("seed", 42), source, "learning.seed"),
    )


def _parse_bootstrap(raw: Mapping[str, Any], source: str) -> int:
    block = _mapping(raw.get("bootstrap"), source, "bootstrap")
    _check_keys(block, ("resamples",), source, "bootstrap")
    return _integer(block.get("resamples", 200), source, "bootstrap.resamples",
                    minimum=1)


def _parse_arc_rule(item: Any, source: str, key: str) -> ArcRule:
    block = _mapping(item, source, key)
    allowed = ("from", "from_layer", "to", "to_layer")
    _check_keys(block, allowed, source, key)

    def end(var_key: str, layer_key: str) -> tuple[str | None, str | None]:
        has_var, has_layer = var_key in block, layer_key in block
        if has_var and has_layer:
            _fail(source, key, f"give either '{var_key}' or '{layer_key}', not both.")
        if not has_var and not has_layer:
            _fail(source, key, f"one of '{var_key}' or '{layer_key}' is missing.")
        if has_var:
            return _text(block[var_key], source, f"{key}.{var_key}"), None
        return None, _text(block[layer_key], source, f"{key}.{layer_key}")

    from_variable, from_layer = end("from", "from_layer")
    to_variable, to_layer = end("to", "to_layer")
    return ArcRule(from_variable, from_layer, to_variable, to_layer)


def _parse_constraints(raw: Mapping[str, Any], source: str) -> Constraints:
    block = _mapping(raw.get("constraints"), source, "constraints")
    _check_keys(block, ("within_layers", "forbid", "require",
                        "no_parents", "no_children"), source, "constraints")
    rules = {
        name: tuple(_parse_arc_rule(item, source, f"constraints.{name}[{i}]")
                    for i, item in enumerate(
                        _list(block.get(name), source, f"constraints.{name}")))
        for name in ("forbid", "require")
    }
    nodes = {
        name: tuple(_text(item, source, f"constraints.{name}[{i}]")
                    for i, item in enumerate(
                        _list(block.get(name), source, f"constraints.{name}")))
        for name in ("no_parents", "no_children")
    }
    return Constraints(
        forbid=rules["forbid"], require=rules["require"],
        no_parents=nodes["no_parents"], no_children=nodes["no_children"],
        within_layers=_boolean(block.get("within_layers", True), source,
                               "constraints.within_layers"),
    )


def _parse_networks(raw: Mapping[str, Any], source: str) -> tuple[NetworkDef, ...]:
    items = _list(raw.get("networks"), source, "networks")
    if not items:
        return (NetworkDef(name="main", description="All variables."),)
    networks: list[NetworkDef] = []
    seen: dict[str, int] = {}
    for i, item in enumerate(items):
        key = f"networks[{i}]"
        block = _mapping(item, source, key)
        _check_keys(block, ("name", "description", "exclude_layers",
                            "exclude_variables", "resamples"), source, key)
        if "name" not in block:
            _fail(source, f"{key}.name", "every network needs a name.")
        name = _text(block["name"], source, f"{key}.name")
        if name in seen:
            _fail(source, f"{key}.name",
                  f"the name {name!r} is already used by networks[{seen[name]}].")
        seen[name] = i
        resamples = block.get("resamples")
        networks.append(NetworkDef(
            name=name,
            description=str(block.get("description", "") or "").strip(),
            exclude_layers=tuple(
                _text(x, source, f"{key}.exclude_layers[{j}]")
                for j, x in enumerate(_list(block.get("exclude_layers"),
                                            source, f"{key}.exclude_layers"))),
            exclude_variables=tuple(
                _text(x, source, f"{key}.exclude_variables[{j}]")
                for j, x in enumerate(_list(block.get("exclude_variables"),
                                            source, f"{key}.exclude_variables"))),
            resamples=(_integer(resamples, source, f"{key}.resamples", minimum=1)
                       if resamples is not None else None),
        ))
    return tuple(networks)


def _names(value: Any, source: str, key: str) -> tuple[str, ...]:
    return tuple(_text(x, source, f"{key}[{i}]")
                 for i, x in enumerate(_list(value, source, key)))


def _parse_analyses(raw: Mapping[str, Any], source: str) -> dict[str, Any]:
    block = _mapping(raw.get("analyses"), source, "analyses")
    _check_keys(block, ("importance", "profiles", "sweep"), source, "analyses")

    imp = _mapping(block.get("importance"), source, "analyses.importance")
    _check_keys(imp, ("targets",), source, "analyses.importance")
    importance = ImportanceSettings(
        targets=_names(imp.get("targets"), source, "analyses.importance.targets"))

    prof = _mapping(block.get("profiles"), source, "analyses.profiles")
    _check_keys(prof, ("network", "resamples", "targets", "groups"),
                source, "analyses.profiles")
    groups = []
    for label, evidence in _mapping(prof.get("groups"), source,
                                    "analyses.profiles.groups").items():
        key = f"analyses.profiles.groups.{label}"
        evidence = _mapping(evidence, source, key)
        if not evidence:
            _fail(source, key, "a profile needs at least one variable and value.")
        groups.append((str(label), dict(evidence)))
    profiles = ProfileSettings(
        groups=tuple(groups),
        targets=_names(prof.get("targets"), source, "analyses.profiles.targets"),
        network=(_text(prof["network"], source, "analyses.profiles.network")
                 if prof.get("network") else None),
        resamples=(_integer(prof["resamples"], source, "analyses.profiles.resamples",
                            minimum=1) if prof.get("resamples") is not None else None),
    )

    sw = _mapping(block.get("sweep"), source, "analyses.sweep")
    _check_keys(sw, ("network", "resamples", "variable", "fixed", "targets"),
                source, "analyses.sweep")
    if sw and "variable" not in sw:
        _fail(source, "analyses.sweep.variable",
              "name the variable that is moved across its states.")
    sweep = SweepSettings(
        variable=_text(sw["variable"], source, "analyses.sweep.variable") if sw else "",
        fixed=dict(_mapping(sw.get("fixed"), source, "analyses.sweep.fixed")),
        targets=_names(sw.get("targets"), source, "analyses.sweep.targets"),
        network=(_text(sw["network"], source, "analyses.sweep.network")
                 if sw.get("network") else None),
        resamples=(_integer(sw["resamples"], source, "analyses.sweep.resamples",
                            minimum=1) if sw.get("resamples") is not None else None),
    )
    return {"importance": importance, "profiles": profiles, "sweep": sweep}
