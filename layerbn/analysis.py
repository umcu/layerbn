"""One object that runs a whole analysis from a project.

    from layerbn.analysis import Analysis

    study = Analysis.from_files("settings.yml")
    study.bins()                  # how every variable was binned
    study.network("main")         # the learned network
    study.stable_edges("main")    # how often each arc appears under resampling
    study.importance("main")      # mutual information with the targets
    study.profiles()              # outcome probabilities for the profiles
    study.sweep()                 # one variable moved across its states

Every method takes its settings from the project (`settings.yml` plus the
design table). Tables use the labels from the design table and readable bin
names. Internally everything is keyed by data column name.

Three things happen here that a direct caller of `layerbn.bn_utils` would
have to do by hand:

* Values in a profile (`AGE: 72`, `SEX: Female`) are converted to the bin or
  category they belong to, and anything that cannot be matched is reported.
* One discretisation is computed from the full data and shared by all
  bootstrap resamples, so that a bin means the same thing in every resample.
* Long bootstraps print progress, so a slow run can be told from a stuck one.
"""
from __future__ import annotations

import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from layerbn._text import did_you_mean
from layerbn.bn_utils import (
    bootstrap_edge_frequencies,
    bootstrap_profile_risks,
    bootstrap_sweep,
    build_bn,
    descendants,
)
from layerbn.discretisation import (
    MISSING,
    describe_template,
    make_type_processor,
    pretty_labels,
    state_for_value,
    with_missing_category,
)
from layerbn.inference import mutual_information_scores, relations_to_target
from layerbn.project import Network, Project, load_project


class DataError(ValueError):
    """Raised when the data file does not match the design."""


# ---------------------------------------------------------------------------
# progress
# ---------------------------------------------------------------------------

class _Progress:
    """A one-line progress bar with an estimate of the time left."""

    def __init__(self, total: int, label: str, *, enabled: bool = True) -> None:
        self.total, self.label, self.enabled = total, label, enabled
        self.count = 0
        self.start = time.monotonic()

    def tick(self) -> None:
        self.count += 1
        if not self.enabled:
            return
        done = min(self.count, self.total)
        # Redrawing one line with a carriage return only works in a terminal.
        # Elsewhere (a log file, a notebook) print at every tenth of the way.
        if not sys.stdout.isatty() and done != 1 and done % max(self.total // 10, 1):
            return
        elapsed = time.monotonic() - self.start
        eta = ""
        if done > 1:
            remaining = elapsed / (done - 1) * (self.total - done)
            eta = (f"  about {remaining / 60:.1f} min left" if remaining > 90
                   else f"  about {remaining:.0f} s left")
        filled = int(24 * done / max(self.total, 1))
        line = (f"  {self.label}: [{'#' * filled}{'.' * (24 - filled)}] "
                f"{done}/{self.total}{eta}")
        if sys.stdout.isatty():
            print(f"\r{line}   ", end="", file=sys.stdout, flush=True)
        else:
            print(line, file=sys.stdout, flush=True)

    def finish(self) -> None:
        if self.enabled:
            minutes = (time.monotonic() - self.start) / 60
            end = "\r" if sys.stdout.isatty() else ""
            print(f"{end}  {self.label}: {self.total} resamples in {minutes:.1f} min"
                  f"{' ' * 30 if end else ''}", file=sys.stdout, flush=True)


# ---------------------------------------------------------------------------
# reading data
# ---------------------------------------------------------------------------

_READERS = {
    ".parquet": "read_parquet", ".csv": "read_csv", ".tsv": "read_csv",
    ".feather": "read_feather", ".sav": "read_spss", ".dta": "read_stata",
    ".xlsx": "read_excel", ".xls": "read_excel",
}


def read_table(path: str | Path) -> pd.DataFrame:
    """Read a data table; the reader is chosen from the file extension."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"data file not found: {path}\n"
            "A relative path is taken relative to the folder of settings.yml. "
            "You can also pass the file on the command line with --data.")
    reader = _READERS.get(path.suffix.lower())
    if reader is None:
        raise ValueError(f"cannot read {path.suffix!r} files. "
                         f"Supported: {sorted(_READERS)}")
    kwargs: dict[str, Any] = {}
    if path.suffix.lower() == ".tsv":
        kwargs = {"sep": "\t"}
    elif path.suffix.lower() == ".csv":
        kwargs = _csv_format(path)
    return getattr(pd, reader)(path, **kwargs)


def _csv_format(path: Path) -> dict[str, Any]:
    """Separator and decimal mark of a CSV file, read from its header line.

    Excel in many countries (the Netherlands, Germany, France, ...) saves CSV
    with semicolons between the columns and a comma as the decimal mark. Read
    such a file with commas and every row becomes one long column.
    """
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        header = handle.readline()
    counts = {sep: header.count(sep) for sep in (",", ";", "\t")}
    sep = max(counts, key=counts.get) if any(counts.values()) else ","
    if sep == ";":
        return {"sep": ";", "decimal": ","}
    return {"sep": sep}


# ---------------------------------------------------------------------------
# the analysis
# ---------------------------------------------------------------------------

class Analysis:
    """A project plus its data, with every analysis step as one call.

    Parameters
    ----------
    project : Project
        From `layerbn.project.load_project`.
    df : DataFrame
        One row per participant, one column per variable.
    verbose : bool
        Print progress and notes. Turn off for scripts.

    Attributes
    ----------
    df : DataFrame
        The data actually analysed: the declared variables, complete cases
        if `data.missing` is `drop_rows`.
    notes : list of str
        Everything worth knowing that is not an error: columns that were not
        used, rows that were dropped, values that were placed in a bin,
        resamples that failed. These are also written to the report.
    """

    def __init__(self, project: Project, df: pd.DataFrame, *, verbose: bool = True) -> None:
        self.project = project
        self.design = project.design
        self.verbose = verbose
        self.notes: list[str] = []

        self.fixed_states: dict[str, list[str]] = {}
        self._bin_overrides: dict[str, int] = {}
        self.df, self.n_input = self._prepare(df)
        self.n = len(self.df)

        self._reset_discretisation()

        self._templates: dict[str, Any] = {}
        self._networks: dict[str, Any] = {}
        self._edge_freqs: dict[str, dict[tuple[str, str], float]] = {}
        self._strengths: dict[str, dict[tuple[str, str], float]] = {}

    # -- construction --------------------------------------------------------

    def _reset_discretisation(self) -> None:
        """(Re)build the binning and forget everything learned with the old one."""
        self.type_processor = make_type_processor(
            self.df, self._design_with_overrides(), self.project.settings.discretisation,
            fixed_states=self.fixed_states)
        self._templates = {}
        self._networks = {}
        self._edge_freqs = {}
        self._strengths = {}

    def _design_with_overrides(self) -> Any:
        if not self._bin_overrides:
            return self.design
        from dataclasses import replace
        variables = tuple(
            replace(v, bins=self._bin_overrides[v.column], cutpoints=())
            if v.column in self._bin_overrides else v for v in self.design.variables)
        return replace(self.design, variables=variables)

    def set_bins(self, bins: Mapping[str, int] | int | None = None,
                 **per_variable: int) -> Analysis:
        """Choose the number of bins per variable, e.g. 4 for quartiles, 5 for quintiles.

        `study.set_bins({"AGE": 5, "MEASURE_1": 4})`, or `study.set_bins(5)` for every
        continuous variable. Variables are named by column or label. This replaces
        bins and cut points from the design table for those variables, and
        discards networks learned with the old bins, so learn again afterwards.
        Returns the analysis, so calls can be chained.
        """
        if isinstance(bins, int):
            bins = {v.column: bins for v in self.design.variables
                    if v.kind == "continuous" or (v.kind is None and pd.api.types.is_numeric_dtype(
                        self.df[v.column]) and self.df[v.column].nunique()
                        > self.project.settings.discretisation.categorical_max_levels)}
        for name, k in {**(bins or {}), **per_variable}.items():
            if int(k) < 2:
                raise ValueError(f"{name}: at least 2 bins are needed, got {k}.")
            self._bin_overrides[self.design.resolve_variable(name)] = int(k)
        if self.project.settings.data.missing == "category":
            self.df, self.fixed_states = self._with_missing_states(self._raw)
        self._reset_discretisation()
        return self

    @classmethod
    def from_files(cls, settings_path: str | Path,
                   data_path: str | Path | None = None, *,
                   verbose: bool = True) -> Analysis:
        """Load the project, then the data file named in it (or `data_path`)."""
        project = load_project(settings_path)
        return cls(project, read_table(project.data_path(data_path)), verbose=verbose)

    def _note(self, message: str) -> None:
        self.notes.append(message)
        if self.verbose:
            print(f"  note: {message}")

    def _prepare(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        """Check the data against the design and return what will be analysed."""
        design = self.design
        missing, unused = design.check_columns(df.columns)
        if missing:
            lines = []
            for column in missing:
                hint = did_you_mean(column, df.columns)
                lines.append(f"  {column}" + (f"  {hint.strip().replace('Did you mean', 'is it')}"
                                               if hint else ""))
            raise DataError(
                f"{len(missing)} variable(s) in the design table are not columns "
                "of the data file:\n" + "\n".join(lines[:25])
                + ("\n  ..." if len(lines) > 25 else "")
                + "\nColumn names must match exactly, including capital letters and "
                  "spaces."
                + (" For repeated measures the column is built from the pattern "
                   f"{design.column_pattern!r} (setting data.column_pattern)."
                   if design.timepoints else ""))
        if unused:
            self._note(f"{len(unused)} column(s) of the data file are not in the design "
                       f"table and are not used: {unused[:10]}"
                       f"{' ...' if len(unused) > 10 else ''}")

        data = df[design.columns].copy()
        n_input = len(data)

        absent = data.isna().sum()
        absent = absent[absent > 0]
        if len(absent):
            if self.project.settings.data.missing == "category":
                self._raw = data
                worst = ", ".join(f"{design.label(c)} ({k / n_input:.0%})"
                                  for c, k in absent.sort_values(ascending=False).head(10).items())
                self._note(f"{len(absent)} variable(s) have missing values, kept as a "
                           f"'{MISSING}' state (data.missing: category): {worst}")
            elif self.project.settings.data.missing == "drop_rows":
                data = data.dropna()
                self._note(
                    f"{n_input - len(data)} of {n_input} participants have a missing "
                    f"value in at least one variable and were removed (data.missing: "
                    f"drop_rows). {len(data)} remain.")
            else:
                worst = absent.sort_values(ascending=False).head(15)
                table = "\n".join(
                    f"  {design.label(c)}: {int(k)} missing ({k / n_input:.0%})"
                    for c, k in worst.items())
                raise DataError(
                    f"The data has missing values in {len(absent)} variable(s):\n"
                    f"{table}\n"
                    "The network is learned from complete data. Either fill in or "
                    "impute the values before the analysis, or set `data: missing: "
                    "drop_rows` in settings.yml to analyse the participants who "
                    "have all values (which can bias results if values are not "
                    "missing at random).")

        constant = [c for c in data.columns if data[c].nunique(dropna=True) < 2]
        if constant:
            raise DataError(
                "These variables have only one value in the data, so they carry no "
                f"information: {[design.label(c) for c in constant]}. Remove them "
                "from the design table.")

        for v in design.variables:
            if v.kind == "continuous" and not pd.api.types.is_numeric_dtype(data[v.column]):
                raise DataError(
                    f"{v.label}: type is 'continuous' but the column is not numeric "
                    f"(it contains {data[v.column].iloc[0]!r}, for example).")
        data = self._whole_numbers_as_integers(data)
        if self.project.settings.data.missing == "category":
            self._raw = data
            data, self.fixed_states = self._with_missing_states(data)
        if len(data) < 50:
            self._note(f"Only {len(data)} participants. Structure learning from so "
                       "few is unreliable.")
        return data.reset_index(drop=True), n_input

    def _with_missing_states(self, data: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, list[str]]]:
        """Give every variable with missing values a `Missing` state."""
        base = self.project.settings.discretisation
        data, states = data.copy(), {}
        for v in self.design.variables:
            if not data[v.column].isna().any():
                continue
            bins = self._bin_overrides.get(v.column, v.bins)
            data[v.column], states[v.column] = with_missing_category(
                data[v.column], kind=v.kind, bins=bins,
                cutpoints=() if v.column in self._bin_overrides else v.cutpoints,
                method=base.method, default_bins=base.bins,
                categorical_max_levels=base.categorical_max_levels)
        return data, states

    def _whole_numbers_as_integers(self, data: pd.DataFrame) -> pd.DataFrame:
        """Store whole-number categories as integers, so they are named `6`, not `6.0`.

        A column that is read as floats (because Excel or a missing value made it
        so) would otherwise get the category names `6.0`, `7.0`, and a profile
        value written as `6` would not match. This applies to columns that are
        used as categories: those marked `categorical`, and numeric columns with
        few distinct values that are not binned.
        """
        limit = self.project.settings.discretisation.categorical_max_levels
        for v in self.design.variables:
            column = data[v.column]
            if not pd.api.types.is_float_dtype(column):
                continue
            binned_by_choice = v.kind == "continuous" or v.bins is not None or v.cutpoints
            as_categories = v.kind == "categorical" or (
                v.kind is None and not binned_by_choice and column.nunique() <= limit)
            if as_categories and (column == column.round()).all():
                data[v.column] = column.astype("int64")
        return data

    # -- naming ----------------------------------------------------------------

    def label(self, column: str) -> str:
        return self.design.label(column)

    def _states(self, network_name: str, column: str) -> dict[str, str]:
        """`{raw state: readable state}` for one variable."""
        template = self.template(network_name)
        labels = list(template.variable(template.idFromName(column)).labels())
        return pretty_labels(labels)

    # -- settings shared by every learning call ------------------------------

    def _network_def(self, name: str | None) -> Network:
        return self.project.network(name)

    def _learn_kwargs(self, network: Network) -> dict[str, Any]:
        p, s = self.project, self.project.settings
        return {
            "layer_map": {k: list(v) for k, v in network.layer_map.items()},
            "type_processor": self.type_processor,
            "score": s.learning.score,
            "search": s.learning.search,
            "max_parents": s.learning.max_parents,
            "no_inner_arcs": [n for n in network.layer_map
                              if not p.arcs_within(n)],
            "forbidden_pairs": p.forbidden_pairs,
            "mandatory_pairs": p.mandatory_pairs,
            "no_parents": p.no_parents,
            "no_children": p.no_children,
            "fixed_template": self.template(network.name),
        }

    def template(self, network_name: str) -> Any:
        """The discretisation of one network, computed once from the full data."""
        if network_name not in self._templates:
            network = self._network_def(network_name)
            self._templates[network_name] = self.type_processor.discretizedTemplate(
                self.df[list(network.columns)])
        return self._templates[network_name]

    def bins(self, network: str | None = None) -> pd.DataFrame:
        """How every variable was binned. Read this before the results."""
        network = self._network_def(network).name
        return describe_template(self.template(network), self.design)

    # -- structure -----------------------------------------------------------

    def network(self, name: str | None = None, *, refresh: bool = False) -> Any:
        """Learn (and keep) the network of one entry in `networks`."""
        definition = self._network_def(name)
        if refresh or definition.name not in self._networks:
            kwargs = self._learn_kwargs(definition)
            layer_map = kwargs.pop("layer_map")
            type_processor = kwargs.pop("type_processor")
            self._networks[definition.name] = build_bn(
                self.df, layer_map, type_processor,
                seed=self.project.settings.learning.seed, **kwargs)
        return self._networks[definition.name]

    def explore(self, network: str | None = None, *, path: str | Path | None = None,
                stability: bool = False, evidence: Mapping[str, Any] | None = None) -> Any:
        """Interactive network: distributions inside the nodes, click to set evidence.

        Shows itself in a notebook. With `path` it is also written as one
        HTML file that opens in any browser. `stability=True` colours arcs by
        their bootstrap frequency (runs the bootstrap if not done yet).
        `evidence` can start the page with states chosen, e.g. `{"AGE": "≥ 72"}`.
        """
        from layerbn.explorer import Explorer, explorer_html, explorer_model
        definition = self._network_def(network)
        start = {}
        for name, value in (evidence or {}).items():
            column = self.design.resolve_variable(name)
            labels = list(self.template(definition.name).variable(column).labels())
            raw = state_for_value(labels, value)
            pretty = self._states(definition.name, column)
            if raw is not None:
                start[column] = [pretty[raw]]
        page = Explorer(explorer_html(
            explorer_model(self, definition.name, stability=stability), start))
        if path is not None:
            page.save(path)
        return page

    def arcs(self, name: str | None = None) -> list[tuple[str, str]]:
        """The arcs of a network as `(parent column, child column)`."""
        bn = self.network(name)
        return [(bn.variable(p).name(), bn.variable(c).name()) for p, c in bn.arcs()]

    def edge_frequencies(self, name: str | None = None, *,
                         refresh: bool = False) -> dict[tuple[str, str], float]:
        """Fraction of bootstrap resamples that contain each arc.

        This is the slow step, and the result is kept, so asking again for a
        table and then a figure costs nothing.
        """
        definition = self._network_def(name)
        if not refresh and definition.name in self._edge_freqs:
            return self._edge_freqs[definition.name]

        progress = _Progress(definition.resamples,
                             f"arc stability [{definition.name}]", enabled=self.verbose)
        kwargs = self._learn_kwargs(definition)
        try:
            result, failed = bootstrap_edge_frequencies(
                self.df, resamples=definition.resamples,
                seed=self.project.settings.learning.seed,
                progress=progress.tick, **kwargs)
        finally:
            progress.finish()
        if failed:
            self._note(f"{failed} of {definition.resamples} bootstrap fits failed "
                       f"for network {definition.name!r}. Frequencies are divided by "
                       "the number of resamples requested, so failures lower them. "
                       "Many failures mean the data are too thin for these settings.")
        self._edge_freqs[definition.name] = result
        return result

    def arc_strengths(self, name: str | None = None) -> dict[tuple[str, str], float]:
        """Mutual information (bits) between parent and child, for each learned arc."""
        import pyagrum as gum

        definition = self._network_def(name)
        if definition.name not in self._strengths:
            bn = self.network(definition.name)
            strengths: dict[tuple[str, str], float] = {}
            for parent, child in bn.arcs():
                p_name, c_name = bn.variable(parent).name(), bn.variable(child).name()
                try:
                    # A new engine per arc: InformationTheory restricts the
                    # engine it is given to that query's variables.
                    info = gum.InformationTheory(gum.LazyPropagation(bn), c_name, [p_name])
                    strengths[(p_name, c_name)] = max(info.mutualInformationXY(), 0.0)
                except Exception:
                    strengths[(p_name, c_name)] = float("nan")
            self._strengths[definition.name] = strengths
        return self._strengths[definition.name]

    def stable_edges(self, name: str | None = None, *,
                     min_frequency: float = 0.0) -> pd.DataFrame:
        """Arc stability as a table, most frequent first.

        `In network` says whether the arc is in the network learned from the
        full data. That is a different question from how often the arc
        survives resampling, and the two can disagree in both directions.
        """
        definition = self._network_def(name)
        frequencies = self.edge_frequencies(definition.name)
        in_network = set(self.arcs(definition.name))
        strengths = self.arc_strengths(definition.name)
        d = self.design

        rows = [{
            "Parent": d.label(p), "Child": d.label(c),
            "Parent layer": d.variable(p).layer, "Child layer": d.variable(c).layer,
            "Frequency": f, "In network": (p, c) in in_network,
            "Mutual information (bits)": strengths.get((p, c), np.nan),
        } for (p, c), f in frequencies.items() if f >= min_frequency]
        columns = ["Parent", "Child", "Parent layer", "Child layer", "Frequency",
                   "In network", "Mutual information (bits)"]
        table = pd.DataFrame(rows, columns=columns)
        return table.sort_values("Frequency", ascending=False).reset_index(drop=True)

    def compare_networks(self, names: Sequence[str] | None = None) -> pd.DataFrame:
        """Arc frequency in each network, side by side.

        Use this to see what changes when a layer or variable is left out.
        An empty cell means the arc did not occur in any resample of that
        network, or the arc is not possible there.
        """
        names = list(names) if names else self.project.network_names
        columns: dict[str, dict[tuple[str, str], float]] = {
            n: self.edge_frequencies(n) for n in names}
        arcs = sorted({arc for freq in columns.values() for arc in freq},
                      key=lambda a: -max(f.get(a, 0.0) for f in columns.values()))
        d = self.design
        rows = [{"Parent": d.label(p), "Child": d.label(c),
                 **{n: columns[n].get(a, np.nan) for n in names}}
                for a in arcs for p, c in [a]]
        return pd.DataFrame(rows, columns=["Parent", "Child", *names])

    # -- interpretation ----------------------------------------------------

    def _targets(self, network: Network, requested: Sequence[str],
                 what: str) -> list[str]:
        """Targets in `network`: those requested, else the default."""
        chosen = list(requested) or list(self.project.default_targets(network))
        present = [t for t in chosen if t in network.columns]
        for t in chosen:
            if t not in network.columns:
                self._note(f"{what}: {self.label(t)} is not in network "
                           f"{network.name!r} and was skipped.")
        return present

    def importance(self, name: str | None = None, *,
                   targets: Sequence[str] | None = None) -> pd.DataFrame:
        """Rank the other variables by mutual information with each target.

        `Mutual information` (bits) is what a variable tells you about the
        target. It includes information that reaches the target through
        other variables, so a variable can rank high without being connected
        to the target directly. `Relation` says how the variable is connected
        to the target in the learned network: `parent`, `child`,
        `co-parent` (shares a child with the target) or `other`. `Arcs` is the
        shortest number of arcs between the two, ignoring direction. Neither
        number is an effect estimate.
        """
        definition = self._network_def(name)
        bn = self.network(definition.name)
        requested = ([self.design.resolve_variable(t) for t in targets]
                     if targets is not None else list(self.project.importance_targets))
        chosen = self._targets(definition, requested, "importance")

        frames = []
        for target in chosen:
            mi = mutual_information_scores(bn, target)
            relations = relations_to_target(bn, target)
            frame = pd.DataFrame({"Mutual information (bits)": mi})
            frame.insert(0, "Target", self.label(target))
            frame.insert(1, "Variable", [self.label(c) for c in frame.index])
            frame.insert(2, "Layer", [self.design.variable(c).layer for c in frame.index])
            frame["Relation"] = [relations[c][0] for c in frame.index]
            frame["Arcs"] = [relations[c][1] for c in frame.index]
            frames.append(frame.reset_index(drop=True))
        columns = ["Target", "Variable", "Layer", "Mutual information (bits)",
                   "Relation", "Arcs"]
        if not frames:
            return pd.DataFrame(columns=columns)
        table = pd.concat(frames, ignore_index=True)
        table["Arcs"] = table["Arcs"].astype("Int64")
        return table.sort_values(["Target", "Mutual information (bits)"],
                                 ascending=[True, False], kind="stable"
                                 ).reset_index(drop=True)

    # -- profiles and sweeps ---------------------------------------------------

    def resolve_profile(self, network_name: str, profile: Mapping[str, Any], *,
                        label: str = "profile") -> dict[str, int]:
        """Convert the values of a profile to state indices.

        `AGE: 72` is placed in the bin that contains 72, a category is matched
        by name, and `"≥ 27"` as printed in the bins table also works. Values
        that cannot be placed are reported and left out.
        """
        network = self._network_def(network_name)
        template = self.template(network.name)
        applied: dict[str, int] = {}
        snapped: list[str] = []
        rejected: list[str] = []

        for column, value in profile.items():
            name = self.label(column)
            if column not in network.columns:
                rejected.append(f"{name}={value!r} (not in network {network.name!r})")
                continue
            labels = list(template.variable(template.idFromName(column)).labels())
            state = state_for_value(labels, value)
            if state is None:
                shown = list(pretty_labels(labels).values())
                rejected.append(f"{name}={value!r} (no such state; states are {shown})")
                continue
            applied[column] = labels.index(state)
            shown = pretty_labels(labels)[state]
            if str(value) != shown:
                snapped.append(f"{name}: {value!r} -> {shown}")
        if snapped:
            self._note(f"{label}: placed in bins: " + "; ".join(snapped))
        if rejected:
            self._note(f"{label}: NOT USED: " + "; ".join(rejected))
        return applied

    def profiles(self, name: str | None = None) -> pd.DataFrame:
        """Probability of each state of the targets, given each profile.

        One row per profile, target and state, with the mean over the
        bootstrap resamples and a 95% percentile interval. The interval
        reflects uncertainty in both the structure and the parameters,
        because each resample learns both again.
        """
        project = self.project
        if not project.profile_groups:
            raise ValueError("No profiles are defined. Add `analyses: profiles: groups:` "
                             "to settings.yml.")
        definition = self._network_def(name or project.profile_network)
        targets = self._targets(definition, list(project.profile_targets), "profiles")
        if not targets:
            raise ValueError("None of the profile targets is in this network.")

        resolved = [(label, self.resolve_profile(definition.name, evidence, label=label))
                    for label, evidence in project.profile_groups]
        empty = [label for label, applied in resolved if not applied]
        if empty:
            raise ValueError(f"No value of the profile(s) {empty} could be used. "
                             "Check names and values against study.bins().")

        n = project.settings.profiles.resamples or definition.resamples
        progress = _Progress(n, f"profiles [{definition.name}]", enabled=self.verbose)
        try:
            table, failed = bootstrap_profile_risks(
                self.df, resamples=n, seed=project.settings.learning.seed,
                progress=progress.tick, profiles=resolved, targets=targets,
                **self._learn_kwargs(definition))
        finally:
            progress.finish()
        if failed:
            self._note(f"{failed} of {n} fits failed in the profile analysis.")

        out = table.copy()
        out["state"] = [self._states(definition.name, t)[s]
                        for t, s in zip(table["target"], table["state"], strict=True)]
        out["target"] = [self.label(t) for t in table["target"]]
        out = out.rename(columns={
            "profile": "Profile", "target": "Target", "state": "State",
            "probability": "Probability", "std": "SD", "ci_low": "CI 2.5%",
            "ci_high": "CI 97.5%", "resamples": "Resamples"})
        return out.sort_values(["Profile", "Target", "State"]).reset_index(drop=True)

    def sweep(self, name: str | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Move one variable across its states with a profile held fixed.

        Returns `(table, meta)`. `meta` carries what the figure needs. A note
        is made if the fixed profile contains a variable downstream of the
        moved one: holding it fixed blocks part of the effect being measured.
        These are conditional probabilities, not effects of an intervention.
        """
        project = self.project
        if not project.sweep_variable:
            raise ValueError("No sweep is defined. Add `analyses: sweep:` to settings.yml.")
        definition = self._network_def(name or project.sweep_network)
        column = project.sweep_variable
        if column not in definition.columns:
            raise ValueError(f"{self.label(column)} is not in network {definition.name!r}.")
        targets = self._targets(definition, list(project.sweep_targets), "sweep")

        template = self.template(definition.name)
        states = list(template.variable(template.idFromName(column)).labels())
        fixed = self.resolve_profile(definition.name, project.sweep_fixed, label="sweep")

        bn = self.network(definition.name)
        below = {bn.variable(i).name() for i in descendants(bn, bn.idFromName(column))}
        blocked = [self.label(c) for c in fixed if c in below]
        if blocked:
            self._note(f"sweep: {blocked} lie downstream of {self.label(column)} in the "
                       "learned network. Holding them fixed blocks part of the effect of "
                       f"{self.label(column)}, and the curves can look flat for that "
                       "reason. Fix only variables upstream of it.")

        n = project.settings.sweep.resamples or definition.resamples
        progress = _Progress(n, f"sweep [{self.label(column)}]", enabled=self.verbose)
        try:
            table, target_states, failed = bootstrap_sweep(
                self.df, resamples=n, seed=project.settings.learning.seed,
                progress=progress.tick, variable=column, variable_states=states,
                fixed=fixed, targets=targets, **self._learn_kwargs(definition))
        finally:
            progress.finish()
        if failed:
            self._note(f"{failed} of {n} fits failed in the sweep.")

        shown = pretty_labels(states)
        out = table.copy()
        out["variable_state"] = out["variable_state"].map(shown)
        out["target_state"] = [self._states(definition.name, t)[s] for t, s in
                               zip(table["target"], table["target_state"], strict=True)]
        out["target"] = [self.label(t) for t in table["target"]]
        meta = {
            "variable": self.label(column),
            "variable_states": [shown[s] for s in states],
            "targets": [self.label(t) for t in targets],
            "target_states": {self.label(t): [self._states(definition.name, t)[s]
                                              for s in target_states[t]]
                              for t in targets},
            "fixed": {self.label(c): project.sweep_fixed.get(c, v)
                      for c, v in fixed.items()},
        }
        return out, meta

    # -- reporting -------------------------------------------------------------

    def summary(self) -> str:
        """Text description of the project and the data."""
        lines = [self.project.summary(), "",
                 f"Data         {self.n} participants, {len(self.df.columns)} variables used"]
        if self.n != self.n_input:
            lines[-1] += f" ({self.n_input - self.n} removed for missing values)"
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (f"<Analysis {self.project.name!r}: {self.n} participants, "
                f"networks {self.project.network_names}>")
