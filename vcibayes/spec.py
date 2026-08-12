"""Analysis-spec loading and validation.

A project's `spec.yml` declares *what the analysis is* — the ordered layers
and their variables, which layers each network variant excludes, the
discretisation, the seed and bootstrap counts, the scenario profiles and the
knob sweep. It deliberately holds no paths: machine-specific locations stay
in `config.yml`, so a spec is shareable as-is.

The spec starts at the analysis-ready dataframe. Preprocessing is not
expressible here and is not meant to be.

    from vcibayes.spec import load_spec
    spec = load_spec("spec.yml")
    spec.layer_map          # {layer name: [variable, ...]}, in spec order
    spec.variant("joint")   # outcomes + exclude_layers for one network

Validation is eager and the errors name the offending key by its path in the
file (`layers[3].variables[1]`), so a typo is found before a 40-minute
bootstrap rather than after it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

SPEC_VERSION = 1

ROLES = ("covariate", "outcome", "selection")
SCORES = ("K2", "BIC", "BDEU")


class SpecError(ValueError):
    """Raised for any malformed spec. The message names the offending key."""


# ---------------------------------------------------------------------------
# small helpers for readable errors
# ---------------------------------------------------------------------------

def _fail(source: str, key: str, message: str) -> None:
    raise SpecError(f"{source}: {key}: {message}")


def _require(raw: Mapping[str, Any], key: str, source: str, parent: str = "") -> Any:
    path = f"{parent}.{key}" if parent else key
    if key not in raw:
        _fail(source, path, "required key is missing")
    return raw[key]


def _as_mapping(value: Any, source: str, key: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(source, key, f"expected a mapping, got {type(value).__name__}")
    return value


def _as_list(value: Any, source: str, key: str) -> list[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(source, key, f"expected a list, got {type(value).__name__}")
    return list(value)


def _as_str(value: Any, source: str, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(source, key, f"expected a non-empty string, got {value!r}")
    return value


def _as_int(value: Any, source: str, key: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(source, key, f"expected an integer, got {value!r}")
    if minimum is not None and value < minimum:
        _fail(source, key, f"must be >= {minimum}, got {value}")
    return value


def _as_bool(value: Any, source: str, key: str) -> bool:
    if not isinstance(value, bool):
        _fail(source, key, f"expected true or false, got {value!r}")
    return value


def _did_you_mean(name: str, candidates: Iterable[str]) -> str:
    """Cheap suggestion so a typo does not turn into a hunt."""
    import difflib
    close = difflib.get_close_matches(name, list(candidates), n=1, cutoff=0.6)
    return f" Did you mean {close[0]!r}?" if close else ""


# ---------------------------------------------------------------------------
# dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Layer:
    name: str
    variables: tuple[str, ...]
    role: str = "covariate"


@dataclass(frozen=True)
class Variant:
    name: str
    outcomes: tuple[str, ...]
    exclude_layers: tuple[str, ...] = ()
    bootstrap_n: int | None = None


@dataclass(frozen=True)
class Discretisation:
    method: str = "quantile"
    n_bins: int = 4
    threshold: int = 10


@dataclass(frozen=True)
class Model:
    score: str = "K2"
    use_tabu: bool = True
    max_indegree: int = 5
    seed: int = 42


@dataclass(frozen=True)
class Scenarios:
    profiles: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    targets: tuple[tuple[str, str], ...] = ()
    bootstrap_n: int | None = None


@dataclass(frozen=True)
class KnobSweep:
    knob: str = ""
    base_profile: Mapping[str, Any] = field(default_factory=dict)
    outcomes: tuple[str, ...] = ()
    bootstrap_n: int | None = None


@dataclass(frozen=True)
class Spec:
    """A validated analysis spec."""

    source: str
    name: str
    description: str
    data_path: str
    layers: tuple[Layer, ...]
    discretisation: Discretisation
    model: Model
    bootstrap_n: int
    variants: tuple[Variant, ...]
    information_targets: tuple[str, ...]
    scenarios: Scenarios
    knob_sweep: KnobSweep

    # -- layer views -------------------------------------------------------

    @property
    def layer_order(self) -> list[str]:
        """Layer names in spec order. **This order is the arc constraint.**"""
        return [layer.name for layer in self.layers]

    @property
    def layer_map(self) -> dict[str, list[str]]:
        """`{layer name: [variable, ...]}` in spec order."""
        return {layer.name: list(layer.variables) for layer in self.layers}

    @property
    def variables(self) -> list[str]:
        return [v for layer in self.layers for v in layer.variables]

    def layer_of(self, variable: str) -> str:
        for layer in self.layers:
            if variable in layer.variables:
                return layer.name
        raise SpecError(
            f"{self.source}: variable {variable!r} is not in any layer."
            f"{_did_you_mean(variable, self.variables)}"
        )

    def layers_with_role(self, role: str) -> list[str]:
        return [layer.name for layer in self.layers if layer.role == role]

    # -- patterns handed to vcibayes.bn_utils ---------------------------------
    # `build_bn` identifies the outcome and dropout layers by substring match
    # on the layer name. Passing the full names of the layers declared with
    # those roles makes the spec, not a naming convention, authoritative.

    @property
    def outcome_patterns(self) -> tuple[str, ...]:
        return tuple(self.layers_with_role("outcome"))

    @property
    def dropout_patterns(self) -> tuple[str, ...]:
        return tuple(self.layers_with_role("selection"))

    # -- variants ----------------------------------------------------------

    def variant(self, name: str) -> Variant:
        for v in self.variants:
            if v.name == name:
                return v
        known = [v.name for v in self.variants]
        raise SpecError(
            f"{self.source}: no variant named {name!r}. "
            f"Defined variants: {known}.{_did_you_mean(name, known)}"
        )

    def bootstrap_for(self, variant_name: str) -> int:
        v = self.variant(variant_name)
        return self.bootstrap_n if v.bootstrap_n is None else v.bootstrap_n


# ---------------------------------------------------------------------------
# loader
# ---------------------------------------------------------------------------

def load_spec(path: str | Path) -> Spec:
    """Read and validate `spec.yml`. Raises `SpecError` with the offending key."""
    path = Path(path)
    if not path.exists():
        raise SpecError(f"spec file not found: {path}")
    source = path.name

    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, Mapping):
        _fail(source, "<root>", "file must contain a mapping at the top level")

    version = raw.get("spec_version", SPEC_VERSION)
    if version != SPEC_VERSION:
        _fail(source, "spec_version",
              f"unsupported version {version!r}; this loader understands {SPEC_VERSION}")

    layers = _parse_layers(raw, source)
    known_vars = [v for layer in layers for v in layer.variables]
    layer_names = [layer.name for layer in layers]

    data = _as_mapping(_require(raw, "data", source), source, "data")
    data_path = _as_str(_require(data, "path", source, "data"), source, "data.path")

    spec = Spec(
        source=source,
        name=_as_str(raw.get("name", path.stem), source, "name"),
        description=str(raw.get("description", "")),
        data_path=data_path,
        layers=layers,
        discretisation=_parse_discretisation(raw, source),
        model=_parse_model(raw, source),
        bootstrap_n=_parse_bootstrap_n(raw, source),
        variants=_parse_variants(raw, source, layer_names, known_vars),
        information_targets=_parse_information(raw, source, known_vars),
        scenarios=_parse_scenarios(raw, source, known_vars),
        knob_sweep=_parse_knob_sweep(raw, source, known_vars),
    )
    _check_roles(spec)
    return spec


def _parse_layers(raw: Mapping[str, Any], source: str) -> tuple[Layer, ...]:
    items = _as_list(_require(raw, "layers", source), source, "layers")
    if not items:
        _fail(source, "layers", "at least one layer is required")

    layers: list[Layer] = []
    seen_names: dict[str, int] = {}
    owner: dict[str, tuple[int, str]] = {}   # variable -> (layer index, layer name)

    for i, item in enumerate(items):
        key = f"layers[{i}]"
        item = _as_mapping(item, source, key)
        name = _as_str(_require(item, "name", source, key), source, f"{key}.name")

        if name in seen_names:
            _fail(source, f"{key}.name",
                  f"duplicate layer name {name!r} (already defined at "
                  f"layers[{seen_names[name]}]). Layer names must be unique.")
        seen_names[name] = i

        role = item.get("role", "covariate")
        if role not in ROLES:
            _fail(source, f"{key}.role",
                  f"unknown role {role!r}; expected one of {list(ROLES)}."
                  f"{_did_you_mean(str(role), ROLES)}")

        variables = _as_list(
            _require(item, "variables", source, key), source, f"{key}.variables")
        if not variables:
            _fail(source, f"{key}.variables",
                  f"layer {name!r} has no variables. Remove the layer or add its variables.")

        cleaned: list[str] = []
        for j, var in enumerate(variables):
            vkey = f"{key}.variables[{j}]"
            var = _as_str(var, source, vkey)
            if var in owner:
                prev_i, prev_name = owner[var]
                _fail(source, vkey,
                      f"variable {var!r} already appears in layers[{prev_i}] "
                      f"({prev_name!r}). A variable must belong to exactly one layer.")
            owner[var] = (i, name)
            cleaned.append(var)

        layers.append(Layer(name=name, variables=tuple(cleaned), role=role))

    return tuple(layers)


def _check_roles(spec: Spec) -> None:
    outcomes = spec.layers_with_role("outcome")
    if not outcomes:
        _fail(spec.source, "layers[].role",
              "no layer declares `role: outcome`. Exactly the layers holding "
              "outcome variables must be marked so the learner can forbid "
              "arcs between outcomes.")
    if len(spec.layers_with_role("selection")) > 1:
        _fail(spec.source, "layers[].role",
              f"more than one layer declares `role: selection`: "
              f"{spec.layers_with_role('selection')}. Only one dropout/selection "
              "layer is supported.")


def _parse_discretisation(raw: Mapping[str, Any], source: str) -> Discretisation:
    d = _as_mapping(raw.get("discretisation", {}), source, "discretisation")
    return Discretisation(
        method=_as_str(d.get("method", "quantile"), source, "discretisation.method"),
        n_bins=_as_int(d.get("n_bins", 4), source, "discretisation.n_bins", minimum=2),
        threshold=_as_int(d.get("threshold", 10), source,
                          "discretisation.threshold", minimum=0),
    )


def _parse_model(raw: Mapping[str, Any], source: str) -> Model:
    m = _as_mapping(raw.get("model", {}), source, "model")
    score = _as_str(m.get("score", "K2"), source, "model.score")
    if score.upper() not in SCORES:
        _fail(source, "model.score",
              f"unsupported score {score!r}; expected one of ['K2', 'BIC', 'BDeu']")
    return Model(
        score=score,
        use_tabu=_as_bool(m.get("use_tabu", True), source, "model.use_tabu"),
        max_indegree=_as_int(m.get("max_indegree", 5), source,
                             "model.max_indegree", minimum=1),
        seed=_as_int(m.get("seed", 42), source, "model.seed"),
    )


def _parse_bootstrap_n(raw: Mapping[str, Any], source: str) -> int:
    b = _as_mapping(raw.get("bootstrap", {}), source, "bootstrap")
    return _as_int(b.get("n", 200), source, "bootstrap.n", minimum=1)


def _parse_variants(raw: Mapping[str, Any], source: str,
                    layer_names: Sequence[str], known_vars: Sequence[str]) -> tuple[Variant, ...]:
    items = _as_list(_require(raw, "variants", source), source, "variants")
    if not items:
        _fail(source, "variants", "at least one variant is required")

    variants: list[Variant] = []
    seen: dict[str, int] = {}
    for i, item in enumerate(items):
        key = f"variants[{i}]"
        item = _as_mapping(item, source, key)
        name = _as_str(_require(item, "name", source, key), source, f"{key}.name")
        if name in seen:
            _fail(source, f"{key}.name",
                  f"duplicate variant name {name!r} (already defined at variants[{seen[name]}])")
        seen[name] = i

        outcomes = _as_list(
            _require(item, "outcomes", source, key), source, f"{key}.outcomes")
        if not outcomes:
            _fail(source, f"{key}.outcomes",
                  f"variant {name!r} lists no outcomes")
        for j, o in enumerate(outcomes):
            o = _as_str(o, source, f"{key}.outcomes[{j}]")
            if o not in known_vars:
                _fail(source, f"{key}.outcomes[{j}]",
                      f"{o!r} is not a variable in any layer.{_did_you_mean(o, known_vars)}")

        excluded = _as_list(item.get("exclude_layers", []), source, f"{key}.exclude_layers")
        for j, layer in enumerate(excluded):
            layer = _as_str(layer, source, f"{key}.exclude_layers[{j}]")
            if layer not in layer_names:
                _fail(source, f"{key}.exclude_layers[{j}]",
                      f"{layer!r} is not a declared layer."
                      f"{_did_you_mean(layer, layer_names)}")

        boot = item.get("bootstrap_n")
        if boot is not None:
            boot = _as_int(boot, source, f"{key}.bootstrap_n", minimum=1)

        variants.append(Variant(name=name, outcomes=tuple(outcomes),
                                exclude_layers=tuple(excluded), bootstrap_n=boot))
    return tuple(variants)


def _parse_information(raw: Mapping[str, Any], source: str,
                       known_vars: Sequence[str]) -> tuple[str, ...]:
    analyses = _as_mapping(raw.get("analyses", {}), source, "analyses")
    info = _as_mapping(analyses.get("information", {}), source, "analyses.information")
    targets = _as_list(info.get("targets", []), source, "analyses.information.targets")
    for j, t in enumerate(targets):
        t = _as_str(t, source, f"analyses.information.targets[{j}]")
        if t not in known_vars:
            _fail(source, f"analyses.information.targets[{j}]",
                  f"{t!r} is not a variable in any layer.{_did_you_mean(t, known_vars)}")
    return tuple(targets)


def _parse_scenarios(raw: Mapping[str, Any], source: str,
                     known_vars: Sequence[str]) -> Scenarios:
    analyses = _as_mapping(raw.get("analyses", {}), source, "analyses")
    sc = _as_mapping(analyses.get("scenarios", {}), source, "analyses.scenarios")
    if not sc:
        return Scenarios()

    key = "analyses.scenarios"
    profiles_raw = _as_mapping(sc.get("profiles", {}), source, f"{key}.profiles")
    profiles: list[tuple[str, Mapping[str, Any]]] = []
    for label, evidence in profiles_raw.items():
        pkey = f"{key}.profiles.{label}"
        evidence = _as_mapping(evidence, source, pkey)
        for var in evidence:
            if var not in known_vars:
                _fail(source, f"{pkey}.{var}",
                      f"{var!r} is not a variable in any layer."
                      f"{_did_you_mean(var, known_vars)}")
        profiles.append((str(label), dict(evidence)))

    targets_raw = _as_list(sc.get("targets", []), source, f"{key}.targets")
    targets: list[tuple[str, str]] = []
    for j, entry in enumerate(targets_raw):
        tkey = f"{key}.targets[{j}]"
        entry = _as_mapping(entry, source, tkey)
        var = _as_str(_require(entry, "variable", source, tkey), source, f"{tkey}.variable")
        if var not in known_vars:
            _fail(source, f"{tkey}.variable",
                  f"{var!r} is not a variable in any layer.{_did_you_mean(var, known_vars)}")
        targets.append((var, _as_str(entry.get("label", var), source, f"{tkey}.label")))

    boot = sc.get("bootstrap_n")
    if boot is not None:
        boot = _as_int(boot, source, f"{key}.bootstrap_n", minimum=1)
    return Scenarios(profiles=tuple(profiles), targets=tuple(targets), bootstrap_n=boot)


def _parse_knob_sweep(raw: Mapping[str, Any], source: str,
                      known_vars: Sequence[str]) -> KnobSweep:
    analyses = _as_mapping(raw.get("analyses", {}), source, "analyses")
    ks = _as_mapping(analyses.get("knob_sweep", {}), source, "analyses.knob_sweep")
    if not ks:
        return KnobSweep()

    key = "analyses.knob_sweep"
    knob = _as_str(_require(ks, "knob", source, key), source, f"{key}.knob")
    if knob not in known_vars:
        _fail(source, f"{key}.knob",
              f"{knob!r} is not a variable in any layer.{_did_you_mean(knob, known_vars)}")

    base = _as_mapping(ks.get("base_profile", {}), source, f"{key}.base_profile")
    for var in base:
        if var not in known_vars:
            _fail(source, f"{key}.base_profile.{var}",
                  f"{var!r} is not a variable in any layer.{_did_you_mean(var, known_vars)}")
    if knob in base:
        _fail(source, f"{key}.base_profile.{knob}",
              f"the knob {knob!r} must not also be fixed in base_profile — "
              "the sweep varies it across all of its states.")

    outcomes = _as_list(ks.get("outcomes", []), source, f"{key}.outcomes")
    for j, o in enumerate(outcomes):
        o = _as_str(o, source, f"{key}.outcomes[{j}]")
        if o not in known_vars:
            _fail(source, f"{key}.outcomes[{j}]",
                  f"{o!r} is not a variable in any layer.{_did_you_mean(o, known_vars)}")

    boot = ks.get("bootstrap_n")
    if boot is not None:
        boot = _as_int(boot, source, f"{key}.bootstrap_n", minimum=1)
    return KnobSweep(knob=knob, base_profile=dict(base),
                     outcomes=tuple(outcomes), bootstrap_n=boot)


# ---------------------------------------------------------------------------
# cross-check against the actual data
# ---------------------------------------------------------------------------

def check_against_dataframe(spec: Spec, columns: Iterable[str]) -> list[str]:
    """Compare the spec's variables with the columns actually present.

    Returns a list of human-readable warnings; does not raise. Call it after
    loading the dataframe so a mismatch surfaces before structure learning.
    """
    columns = list(columns)
    warnings: list[str] = []
    missing = [v for v in spec.variables if v not in columns]
    if missing:
        warnings.append(
            f"{len(missing)} variable(s) in {spec.source} are not columns in the "
            f"dataframe and will be silently ignored by the learner: {missing}")
    unassigned = [c for c in columns if c not in spec.variables]
    if unassigned:
        warnings.append(
            f"{len(unassigned)} column(s) in the dataframe are in no layer: "
            f"{unassigned}. Passed to `build_bn` they become nodes that the "
            f"layer constraint isolates, since it permits no arc to or from a "
            f"variable with no layer. `vcibayes.analysis.Analysis` drops them "
            f"instead, so the network matches the spec.")
    return warnings
