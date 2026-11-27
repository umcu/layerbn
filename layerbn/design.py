"""The study design: variables, layers and time points.

The design is kept in a table, not in code. In an Excel workbook it is three
sheets (`variables`, `layers`, `timepoints`); as CSV it is `variables.csv`
with optional `layers.csv` and `timepoints.csv` beside it.

`variables`
    One row per variable: the column name in the data, an optional label,
    the layer it belongs to, and optional per-variable settings (type, number
    of bins, cut points, time points, whether it is a target).
`layers`
    One row per layer, **in causal order**. An arc may only run from a layer
    to itself or to a layer further down this list. A layer can be marked as
    repeated, meaning it is measured at every time point.
`timepoints`
    The measurement occasions, in time order, for repeated layers.

Most designs have no repeated layers: every variable is one data column.
Only if the same variables were measured more than once, a layer can be marked
repeated. `variables` then lists each of its variables once, and the data
columns are generated from the time points, so `SCORE` at time points `T0` and
`T1` refers to the columns `SCORE_T0` and `SCORE_T1`. The layers are generated
in time order: with layers `Background`, `Scores` (repeated), `Status`
(repeated) and time points `T0`, `T1`, the order becomes Background,
Scores T0, Status T0, Scores T1, Status T1.

    from layerbn.design import load_design
    design = load_design("variables.xlsx")
    design.layer_map     # {layer name: [column, ...]} in causal order
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pandas as pd

from layerbn._text import did_you_mean

DEFAULT_COLUMN_PATTERN = "{variable}_{time}"

KINDS = ("continuous", "categorical")

# The categorical palette used for layers, in fixed order. Checked against a
# white background for lightness, chroma and colour-vision-deficiency
# separation of neighbouring colours. Layers are always named directly in
# the figures, so identity does not rely on colour alone.
LAYER_COLOURS = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
    "#e87ba4", "#008300", "#6250d6", "#e34948",
)

_NOTE_COLUMNS = re.compile(r"^(note|notes|comment|comments|remark|remarks|#.*)$")


class DesignError(ValueError):
    """Raised for a problem in the design tables. The message says where."""


# ---------------------------------------------------------------------------
# data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TimePoint:
    key: str            # as used in the data column names, e.g. "T0"
    label: str          # as shown to readers, e.g. "Baseline"


@dataclass(frozen=True)
class LayerDef:
    """A layer as written in the `layers` table."""

    key: str
    label: str
    repeated: bool = False
    arcs_within: bool | None = None   # None: use the settings default
    colour: str | None = None


@dataclass(frozen=True)
class VariableDef:
    """A variable as written in the `variables` table."""

    name: str
    label: str
    layer: str
    kind: str | None = None           # None: decide from the data
    bins: int | None = None
    cutpoints: tuple[float, ...] = ()
    times: tuple[str, ...] | None = None
    target: bool = False


@dataclass(frozen=True)
class Layer:
    """One layer of the network, after time points have been expanded."""

    name: str                         # unique, e.g. "Exposures", or "Scores (First visit)"
    key: str                          # the layer's name in the table
    title: str                        # label of the layer, without the time point
    time: str | None                  # time point label, if the layer is repeated
    variables: tuple[str, ...]        # data column names
    arcs_within: bool | None = None
    colour: str = LAYER_COLOURS[0]


@dataclass(frozen=True)
class Variable:
    """One variable of the network, i.e. one data column."""

    column: str
    label: str                        # unique, includes the time point if any
    short_label: str                  # without the time point
    layer: str                        # name of the layer it sits in
    time: str | None = None
    kind: str | None = None
    bins: int | None = None
    cutpoints: tuple[float, ...] = ()
    target: bool = False


# ---------------------------------------------------------------------------
# the design
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Design:
    """Variables and layers, in causal order, with time points expanded."""

    source: str
    layers: tuple[Layer, ...]
    variables: tuple[Variable, ...]
    timepoints: tuple[TimePoint, ...] = ()
    column_pattern: str = DEFAULT_COLUMN_PATTERN
    warnings: tuple[str, ...] = field(default_factory=tuple)

    # -- views ---------------------------------------------------------------

    @property
    def layer_names(self) -> list[str]:
        return [layer.name for layer in self.layers]

    @property
    def layer_map(self) -> dict[str, list[str]]:
        """`{layer name: [column, ...]}` in causal order."""
        return {layer.name: list(layer.variables) for layer in self.layers}

    @property
    def columns(self) -> list[str]:
        return [v.column for v in self.variables]

    @property
    def targets(self) -> list[str]:
        """Columns flagged as targets in the table, in layer order."""
        return [v.column for v in self.variables if v.target]

    def variable(self, column: str) -> Variable:
        for v in self.variables:
            if v.column == column:
                return v
        raise DesignError(f"{self.source}: no variable with column {column!r}."
                          f"{did_you_mean(column, self.columns)}")

    def layer(self, name: str) -> Layer:
        for layer in self.layers:
            if layer.name == name:
                return layer
        raise DesignError(f"{self.source}: no layer named {name!r}."
                          f"{did_you_mean(name, self.layer_names)}")

    def label(self, column: str) -> str:
        return self.variable(column).label

    def layer_index(self, column: str) -> int:
        name = self.variable(column).layer
        return self.layer_names.index(name)

    # -- name resolution -----------------------------------------------------

    def resolve_variable(self, text: str, *, where: str = "") -> str:
        """Return the column for a column name or a label.

        Column names are tried first, then labels, then labels ignoring case.
        """
        text = str(text)
        columns = self.columns
        if text in columns:
            return text
        by_label = {v.label: v.column for v in self.variables}
        if text in by_label:
            return by_label[text]
        lowered = {v.label.lower(): v.column for v in self.variables}
        lowered.update({c.lower(): c for c in columns})
        if text.lower() in lowered:
            return lowered[text.lower()]
        prefix = f"{where}: " if where else ""
        raise DesignError(
            f"{prefix}{text!r} is not a variable in the design."
            f"{did_you_mean(text, columns + list(by_label))}")

    def resolve_layers(self, text: str, *, where: str = "") -> list[str]:
        """Return the layer names a layer reference stands for.

        A reference may be the name of one layer after expansion
        (`Scores (First visit)`), or the name of a repeated layer in the
        table (`Scores`), which stands for it at every time point.
        """
        text = str(text)
        names = self.layer_names
        if text in names:
            return [text]
        matches = [layer.name for layer in self.layers
                   if text in (layer.key, layer.title)]
        if matches:
            return matches
        prefix = f"{where}: " if where else ""
        keys = sorted({layer.key for layer in self.layers} | set(names))
        raise DesignError(f"{prefix}{text!r} is not a layer in the design."
                          f"{did_you_mean(text, keys)}")

    # -- reporting -----------------------------------------------------------

    def table(self) -> pd.DataFrame:
        """One row per variable, in causal order, for display and reports."""
        rows = []
        for i, layer in enumerate(self.layers, start=1):
            for column in layer.variables:
                v = self.variable(column)
                rows.append({
                    "Order": i,
                    "Layer": layer.title,
                    "Time point": layer.time or "",
                    "Variable": v.label,
                    "Column": v.column,
                    "Target": "yes" if v.target else "",
                })
        return pd.DataFrame(rows)

    def check_columns(self, columns: Iterable[str]) -> tuple[list[str], list[str]]:
        """Return `(missing, unused)` columns, comparing the design with data."""
        columns = list(columns)
        known = set(self.columns)
        missing = [c for c in self.columns if c not in columns]
        unused = [c for c in columns if c not in known]
        return missing, unused


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _clean(value: Any) -> str | None:
    """A cell as stripped text; empty cells become None."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _getter(row: Any):
    """`get(name)`: the cell of this row in column `name`, or None if there is no such column."""
    def get(name: str) -> Any:
        return row[name] if name in row.index else None
    return get


def _flag(value: Any, where: str, *, default: bool | None) -> bool | None:
    text = _clean(value)
    if text is None:
        return default
    lowered = text.lower()
    if lowered in ("yes", "y", "true", "1", "ja", "x"):
        return True
    if lowered in ("no", "n", "false", "0", "nee"):
        return False
    raise DesignError(f"{where}: expected yes or no, got {text!r}.")


def _number(text: str, where: str) -> float:
    try:
        return float(text.replace(",", "."))
    except ValueError:
        raise DesignError(f"{where}: {text!r} is not a number.") from None


def _normalise_header(name: Any) -> str:
    return re.sub(r"\s+", "_", str(name).strip().lower())


# ---------------------------------------------------------------------------
# reading the tables
# ---------------------------------------------------------------------------

_VARIABLE_COLUMNS = ("variable", "label", "layer", "type", "bins",
                     "cutpoints", "times", "target")
_LAYER_COLUMNS = ("layer", "label", "repeated", "arcs_within", "colour")
_TIME_COLUMNS = ("time", "label")


def _prepare(frame: pd.DataFrame, sheet: str, source: str,
             known: Sequence[str], required: Sequence[str]) -> pd.DataFrame:
    """Normalise headers, reject unknown ones and drop empty rows."""
    frame = frame.copy()
    frame.columns = [_normalise_header(c) for c in frame.columns]
    frame = frame.loc[:, [c for c in frame.columns if not c.startswith("unnamed")]]

    for column in frame.columns:
        if column in known or _NOTE_COLUMNS.match(column):
            continue
        raise DesignError(
            f"{source}, sheet '{sheet}': unknown column {column!r}. "
            f"Columns are: {', '.join(known)}. Columns named 'note' or "
            f"'comment' are ignored.{did_you_mean(column, known)}")
    for column in required:
        if column not in frame.columns:
            raise DesignError(
                f"{source}, sheet '{sheet}': the column '{column}' is missing.")

    keep = [c for c in frame.columns if c in known]
    frame = frame[keep].astype(object).where(frame[keep].notna(), None)
    empty = frame.apply(lambda row: all(_clean(v) is None for v in row), axis=1)
    return frame[~empty]


def _read_csv(path: Path) -> pd.DataFrame:
    """Read a table as text. The delimiter is a tab, a semicolon or a comma.

    Excel in many countries (including the Netherlands) saves CSV with
    semicolons, so the first line decides instead of assuming a comma.
    """
    with path.open(encoding="utf-8-sig") as handle:
        header = handle.readline()
    if path.suffix.lower() == ".tsv" or "\t" in header:
        sep = "\t"
    elif header.count(";") > header.count(","):
        sep = ";"
    else:
        sep = ","
    return pd.read_csv(path, dtype=str, keep_default_na=False, sep=sep,
                       encoding="utf-8-sig")


def read_tables(path: str | Path) -> dict[str, pd.DataFrame | None]:
    """Read the design tables from an Excel workbook or from CSV files."""
    path = Path(path)
    if not path.exists():
        raise DesignError(f"design file not found: {path}")
    source = path.name
    suffix = path.suffix.lower()

    raw: dict[str, pd.DataFrame | None] = {
        "variables": None, "layers": None, "timepoints": None}

    if suffix in (".xlsx", ".xlsm", ".xls"):
        sheets = pd.read_excel(path, sheet_name=None, dtype=str,
                               keep_default_na=False)
        canonical = {"variables": "variables", "layers": "layers",
                     "timepoints": "timepoints", "time_points": "timepoints",
                     "time": "timepoints"}
        for name, frame in sheets.items():
            key = canonical.get(_normalise_header(name))
            if key is not None:
                raw[key] = frame
        if raw["variables"] is None:
            raise DesignError(
                f"{source}: there is no sheet named 'variables'. "
                f"The sheets found are {list(sheets)}.")
    elif suffix in (".csv", ".tsv"):
        raw["variables"] = _read_csv(path)
        for name in ("layers", "timepoints"):
            sibling = path.with_name(f"{name}{suffix}")
            if sibling.exists():
                raw[name] = _read_csv(sibling)
    else:
        raise DesignError(
            f"{source}: cannot read a {suffix!r} file. Use .xlsx or .csv.")
    return raw


# ---------------------------------------------------------------------------
# parsing the rows
# ---------------------------------------------------------------------------

def _parse_timepoints(frame: pd.DataFrame | None, source: str) -> tuple[TimePoint, ...]:
    if frame is None:
        return ()
    frame = _prepare(frame, "timepoints", source, _TIME_COLUMNS, ("time",))
    points: list[TimePoint] = []
    seen: set[str] = set()
    for i, row in frame.iterrows():
        where = f"{source}, sheet 'timepoints', row {i + 2}"
        key = _clean(row["time"])
        if key is None:
            raise DesignError(f"{where}: 'time' is empty.")
        if key in seen:
            raise DesignError(f"{where}: time point {key!r} is listed twice.")
        seen.add(key)
        label = _clean(row["label"]) if "label" in frame.columns else None
        points.append(TimePoint(key=key, label=label or key))
    labels = [p.label for p in points]
    for p in points:
        if labels.count(p.label) > 1:
            raise DesignError(
                f"{source}, sheet 'timepoints': the label {p.label!r} is used "
                "more than once. Labels must be different.")
    return tuple(points)


def _parse_layers(frame: pd.DataFrame | None, source: str) -> list[LayerDef] | None:
    if frame is None:
        return None
    frame = _prepare(frame, "layers", source, _LAYER_COLUMNS, ("layer",))
    layers: list[LayerDef] = []
    seen: dict[str, int] = {}
    for i, row in frame.iterrows():
        where = f"{source}, sheet 'layers', row {i + 2}"
        key = _clean(row["layer"])
        if key is None:
            raise DesignError(f"{where}: 'layer' is empty.")
        if key in seen:
            raise DesignError(
                f"{where}: layer {key!r} is listed twice (first on row "
                f"{seen[key] + 2}).")
        seen[key] = i
        get = _getter(row)
        layers.append(LayerDef(
            key=key,
            label=_clean(get("label")) or key,
            repeated=bool(_flag(get("repeated"), f"{where}, column 'repeated'",
                                default=False)),
            arcs_within=_flag(get("arcs_within"),
                              f"{where}, column 'arcs_within'", default=None),
            colour=_clean(get("colour")),
        ))
    return layers


def _parse_variables(frame: pd.DataFrame, source: str,
                     time_keys: Sequence[str]) -> list[VariableDef]:
    frame = _prepare(frame, "variables", source, _VARIABLE_COLUMNS,
                     ("variable", "layer"))
    variables: list[VariableDef] = []
    seen: dict[str, int] = {}
    for i, row in frame.iterrows():
        where = f"{source}, sheet 'variables', row {i + 2}"
        get = _getter(row)

        name = _clean(row["variable"])
        layer = _clean(row["layer"])
        if name is None:
            raise DesignError(f"{where}: 'variable' is empty.")
        if layer is None:
            raise DesignError(f"{where}: variable {name!r} has no layer.")
        if name in seen:
            raise DesignError(
                f"{where}: variable {name!r} is listed twice (first on row "
                f"{seen[name] + 2}). Each variable belongs to one layer.")
        seen[name] = i

        kind = _clean(get("type"))
        if kind is not None:
            kind = kind.lower()
            if kind not in KINDS:
                raise DesignError(
                    f"{where}, column 'type': {kind!r} is not allowed. Use one "
                    f"of {list(KINDS)}, or leave it empty to decide from the "
                    f"data.{did_you_mean(kind, KINDS)}")

        bins_text = _clean(get("bins"))
        bins = None
        if bins_text is not None:
            bins_value = _number(bins_text, f"{where}, column 'bins'")
            if bins_value != int(bins_value) or bins_value < 2:
                raise DesignError(
                    f"{where}, column 'bins': expected a whole number of at "
                    f"least 2, got {bins_text!r}.")
            bins = int(bins_value)

        cut_text = _clean(get("cutpoints"))
        cutpoints: tuple[float, ...] = ()
        if cut_text is not None:
            parts = [p.strip() for p in cut_text.split(";") if p.strip()]
            cutpoints = tuple(sorted({
                _number(p, f"{where}, column 'cutpoints'") for p in parts}))
            if not cutpoints:
                raise DesignError(f"{where}, column 'cutpoints': no values found.")

        if bins is not None and cutpoints:
            raise DesignError(
                f"{where}: give either 'bins' or 'cutpoints', not both.")
        if kind == "categorical" and (bins is not None or cutpoints):
            raise DesignError(
                f"{where}: a categorical variable is not binned, so 'bins' "
                "and 'cutpoints' must be empty.")

        times_text = _clean(get("times"))
        times = None
        if times_text is not None:
            times = tuple(t.strip() for t in re.split(r"[;,]", times_text)
                          if t.strip())
            for t in times:
                # With no time points at all, build_design gives the clearer
                # message that the repeated layer has none.
                if time_keys and t not in time_keys:
                    raise DesignError(
                        f"{where}, column 'times': {t!r} is not on the "
                        f"'timepoints' sheet.{did_you_mean(t, time_keys)}")

        variables.append(VariableDef(
            name=name,
            label=_clean(get("label")) or name,
            layer=layer,
            kind=kind,
            bins=bins,
            cutpoints=cutpoints,
            times=times,
            target=bool(_flag(get("target"), f"{where}, column 'target'",
                              default=False)),
        ))
    if not variables:
        raise DesignError(f"{source}, sheet 'variables': no variables found.")
    return variables


# ---------------------------------------------------------------------------
# building the design
# ---------------------------------------------------------------------------

def _colour_for(index: int) -> str:
    colour = LAYER_COLOURS[index % len(LAYER_COLOURS)]
    if index < len(LAYER_COLOURS):
        return colour
    # More layers than palette slots: reuse the hue, lightened, so that two
    # layers never share exactly the same colour. Layers are labelled in the
    # figures, so identity does not depend on the colour alone.
    rgb = [int(colour[i:i + 2], 16) for i in (1, 3, 5)]
    mixed = [round(c + (255 - c) * 0.45) for c in rgb]
    return "#" + "".join(f"{c:02x}" for c in mixed)


def _check_colour(text: str, where: str) -> str:
    from matplotlib.colors import is_color_like, to_hex
    if not is_color_like(text):
        raise DesignError(
            f"{where}: {text!r} is not a colour. Use a name such as 'steelblue' "
            "or a hex code such as '#2a78d6'.")
    return to_hex(text)


def build_design(
    variables: Sequence[VariableDef],
    layers: Sequence[LayerDef] | None = None,
    timepoints: Sequence[TimePoint] = (),
    *,
    column_pattern: str = DEFAULT_COLUMN_PATTERN,
    source: str = "design",
) -> Design:
    """Validate the tables and expand repeated layers over the time points."""
    warnings: list[str] = []
    timepoints = tuple(timepoints)

    # Layers: from the table if there is one, otherwise by first appearance.
    if layers is None:
        order: list[str] = []
        for v in variables:
            if v.layer not in order:
                order.append(v.layer)
        layer_defs = [LayerDef(key=k, label=k) for k in order]
    else:
        layer_defs = list(layers)
        known = [layer.key for layer in layer_defs]
        for v in variables:
            if v.layer not in known:
                raise DesignError(
                    f"{source}, sheet 'variables': variable {v.name!r} is in "
                    f"layer {v.layer!r}, which is not on the 'layers' sheet."
                    f"{did_you_mean(v.layer, known)}")
    layer_by_key = {layer.key: layer for layer in layer_defs}

    for layer in layer_defs:
        if not any(v.layer == layer.key for v in variables):
            raise DesignError(
                f"{source}, sheet 'layers': layer {layer.key!r} has no variables. "
                "Remove it from the sheet, or add its variables.")

    repeated = [i for i, layer in enumerate(layer_defs) if layer.repeated]
    if repeated and not timepoints:
        names = [layer_defs[i].key for i in repeated]
        raise DesignError(
            f"{source}: the layer(s) {names} are marked as repeated, but there "
            "is no 'timepoints' sheet. Add one listing the time points.")
    if timepoints and not repeated:
        warnings.append(
            "Time points are defined, but no layer is marked as repeated, so "
            "they are not used.")
    if repeated and repeated != list(range(repeated[0], repeated[-1] + 1)):
        raise DesignError(
            f"{source}, sheet 'layers': repeated layers must follow each other "
            "without a layer in between, because together they are expanded "
            f"into one block per time point. Repeated layers: "
            f"{[layer_defs[i].key for i in repeated]}.")

    for v in variables:
        if v.times is not None and not layer_by_key[v.layer].repeated:
            raise DesignError(
                f"{source}, sheet 'variables': variable {v.name!r} has 'times' "
                f"set, but its layer {v.layer!r} is not repeated.")

    # Expand.
    expanded_layers: list[Layer] = []
    expanded_vars: list[Variable] = []
    base_index = {layer.key: i for i, layer in enumerate(layer_defs)}
    sequence: list[tuple[LayerDef, TimePoint | None]] = []
    index = 0
    while index < len(layer_defs):
        if layer_defs[index].repeated:
            block = [layer for layer in layer_defs[index:] if layer.repeated]
            for t in timepoints:
                sequence.extend((layer, t) for layer in block)
            index += len(block)
        else:
            sequence.append((layer_defs[index], None))
            index += 1

    for layer_def, t in sequence:
        members: list[Variable] = []
        for v in (x for x in variables if x.layer == layer_def.key):
            if t is None:
                column, label = v.name, v.label
            else:
                if v.times is not None and t.key not in v.times:
                    continue
                try:
                    column = column_pattern.format(variable=v.name, time=t.key)
                except (KeyError, IndexError):
                    raise DesignError(
                        f"{source}: the column pattern {column_pattern!r} may "
                        "only use {variable} and {time}.") from None
                label = f"{v.label}, {t.label}"
            members.append(Variable(
                column=column, label=label, short_label=v.label,
                layer="", time=t.label if t else None,
                kind=v.kind, bins=v.bins, cutpoints=v.cutpoints, target=v.target))
        if not members:
            continue

        name = layer_def.key if t is None else f"{layer_def.key} ({t.label})"
        title = layer_def.label
        colour_text = layer_def.colour
        colour = (_check_colour(colour_text, f"{source}, sheet 'layers', "
                                f"layer {layer_def.key!r}, column 'colour'")
                  if colour_text else _colour_for(base_index[layer_def.key]))
        expanded_layers.append(Layer(
            name=name, key=layer_def.key, title=title,
            time=t.label if t else None,
            variables=tuple(m.column for m in members),
            arcs_within=layer_def.arcs_within, colour=colour))
        expanded_vars.extend(replace(m, layer=name) for m in members)

    # Uniqueness after expansion.
    for what, values in (("column", [v.column for v in expanded_vars]),
                         ("label", [v.label for v in expanded_vars]),
                         ("layer name", [layer.name for layer in expanded_layers])):
        duplicates = sorted({x for x in values if values.count(x) > 1})
        if duplicates:
            raise DesignError(
                f"{source}: the {what} {duplicates[0]!r} appears more than once "
                f"after the time points are expanded. Each {what} must be "
                "unique.")
    clash = set(v.label for v in expanded_vars) & set(v.column for v in expanded_vars)
    for text in sorted(clash):
        owner = next(v for v in expanded_vars if v.column == text)
        if owner.label != text:
            raise DesignError(
                f"{source}: {text!r} is the column of one variable and the "
                "label of another, so it cannot be used to refer to either. "
                "Change the label.")

    return Design(
        source=source,
        layers=tuple(expanded_layers),
        variables=tuple(expanded_vars),
        timepoints=timepoints,
        column_pattern=column_pattern,
        warnings=tuple(warnings),
    )


def load_design(path: str | Path, *,
                column_pattern: str = DEFAULT_COLUMN_PATTERN) -> Design:
    """Read the design tables and return the expanded, validated design."""
    path = Path(path)
    tables = read_tables(path)
    source = path.name
    timepoints = _parse_timepoints(tables["timepoints"], source)
    layers = _parse_layers(tables["layers"], source)
    variables = _parse_variables(tables["variables"], source,
                                 [t.key for t in timepoints])
    return build_design(variables, layers, timepoints,
                        column_pattern=column_pattern, source=source)


def design_from_layers(
    layers: Mapping[str, Sequence[str]],
    *,
    targets: Iterable[str] = (),
    source: str = "design",
) -> Design:
    """Build a design from a `{layer: [column, ...]}` mapping, in layer order.

    For scripts and tests that have no table. No time points, no labels.
    """
    targets = set(targets)
    variables = [VariableDef(name=v, label=v, layer=layer, target=v in targets)
                 for layer, members in layers.items() for v in members]
    return build_design(variables, [LayerDef(key=k, label=k) for k in layers],
                        source=source)
