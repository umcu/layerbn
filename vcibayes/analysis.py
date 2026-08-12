"""One object that runs a whole analysis from a spec.

The functions in `bn_utils`, `inference` and `plotting` each take the layer
map, the discretisation, the score, the seed and the layer-role patterns as
separate arguments. That is the right shape for a library, but it means a
caller repeats the same eight settings at every call site and any one of
them can silently disagree with the spec.

`Analysis` closes that gap. It holds the spec and the data, and every method
takes its settings from the spec:

    from vcibayes.analysis import Analysis

    study = Analysis.from_files("spec.yml", "cohort.parquet")
    bn = study.network("main")
    edges = study.stable_edges("main")
    risks = study.scenarios("main")

Nothing here implements new statistics. Each method delegates to the same
functions a direct caller would use, with the arguments filled in from the
spec. Three things it does add, all of which are corrections rather than
choices:

* **Evidence is resolved to state indices.** pyAgrum reads a bare integer as
  a state index, so `AGE: 72` in a profile means "state number 72" and
  raises. `bootstrap_scenario_risks` catches that and skips the scenario, so
  the result is a missing row rather than an error. Resolving values here
  makes `72` and `"72"` both mean the age 72, and reports anything it could
  not match instead of dropping it.
* **A fixed discretisation template is shared across bootstrap resamples.**
  Otherwise each resample computes its own quantile edges, and a fixed
  profile refers to a slightly different group of people in every resample.
* **Long bootstraps report progress**, because a cell that prints nothing
  for forty minutes is indistinguishable from a hung kernel.

See `docs/troubleshooting.md` for what the warnings mean.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from vcibayes.bn_utils import (
    bootstrap_edge_frequencies,
    bootstrap_knob_sweep,
    bootstrap_scenario_risks,
    build_bn,
)
from vcibayes.discretisation import describe_template, make_type_processor, state_for_value
from vcibayes.inference import (
    conditional_mutual_information_scores,
    mutual_information_scores,
)
from vcibayes.plotting import build_node_colors, default_layer_colors, plot_knob_sweep
from vcibayes.spec import Spec, check_against_dataframe, load_spec


# ---------------------------------------------------------------------------
# progress reporting
# ---------------------------------------------------------------------------

class _Progress:
    """Print a one-line progress counter with an estimated finish time."""

    def __init__(self, total: int, label: str, *, enabled: bool = True) -> None:
        self.total = total
        self.label = label
        self.enabled = enabled
        self.count = 0
        self.start = time.monotonic()

    def wrap(self, func: Any) -> Any:
        """Return `func` with a progress tick attached to each call."""
        if not self.enabled:
            return func

        def counted(*args: Any, **kwargs: Any) -> Any:
            self.count += 1
            self._draw()
            return func(*args, **kwargs)

        return counted

    def _draw(self) -> None:
        done = min(self.count, self.total)
        elapsed = time.monotonic() - self.start
        if done > 1:
            remaining = elapsed / (done - 1) * (self.total - done)
            eta = f"  ~{remaining / 60:.1f} min left" if remaining > 90 else \
                  f"  ~{remaining:.0f} s left"
        else:
            eta = ""
        bar_width = 24
        filled = int(bar_width * done / max(self.total, 1))
        bar = "#" * filled + "." * (bar_width - filled)
        print(f"\r  {self.label}: [{bar}] {done}/{self.total}{eta}   ",
              end="", file=sys.stdout, flush=True)

    def finish(self) -> None:
        if not self.enabled:
            return
        elapsed = time.monotonic() - self.start
        print(f"\r  {self.label}: done, {self.total} fits in {elapsed / 60:.1f} min"
              f"{' ' * 24}", file=sys.stdout, flush=True)


# ---------------------------------------------------------------------------
# the facade
# ---------------------------------------------------------------------------

class Analysis:
    """A spec plus a dataframe, with every analysis step as one call.

    Parameters
    ----------
    spec : Spec
        Loaded via `vcibayes.spec.load_spec`.
    df : DataFrame
        Analysis-ready and fully imputed. The package does no preprocessing;
        see the scope note in the README.
    verbose : bool
        Print progress and warnings. Turn off for scripted runs.

    Attributes
    ----------
    data_warnings : list of str
        Mismatches between the spec's variables and the dataframe's columns,
        from `check_against_dataframe`. Empty is what you want.
    """

    def __init__(self, spec: Spec, df: pd.DataFrame, *, verbose: bool = True) -> None:
        self.spec = spec
        self.source_df = df
        self.verbose = verbose

        self.type_processor = make_type_processor(
            method=spec.discretisation.method,
            n_bins=spec.discretisation.n_bins,
            threshold=spec.discretisation.threshold,
        )

        self.data_warnings = check_against_dataframe(spec, df.columns)

        # Use exactly the variables the spec declares. A column in no layer
        # would otherwise reach the learner, where the layer constraint
        # forbids every arc touching it, and it would appear in the figure
        # as an isolated node. Dropping it here makes the network match the
        # spec, which is what a reader of the spec expects.
        missing = [v for v in spec.variables if v not in df.columns]
        declared = [v for v in spec.variables if v in df.columns]
        set_aside = [c for c in df.columns if c not in spec.variables]
        self.df = df[declared].copy()

        if self.verbose:
            if missing:
                print(f"MISSING from the data ({len(missing)}): {missing}\n"
                      "  These are declared in the spec but are not columns in the "
                      "dataframe. They cannot be modelled. Fix the spec or the data.")
            if set_aside:
                print(f"Not in any layer, set aside ({len(set_aside)}): {set_aside}\n"
                      "  Add them to a layer in the spec if they belong in the network.")

        self._networks: dict[str, Any] = {}
        self._templates: dict[str, Any] = {}
        self._edge_freqs: dict[str, dict[tuple[str, str], float]] = {}

    # -- construction ------------------------------------------------------

    @classmethod
    def from_files(
        cls,
        spec_path: str | Path,
        data_path: str | Path,
        *,
        verbose: bool = True,
    ) -> "Analysis":
        """Load a spec and a dataframe from disk.

        `data_path` may be any format pandas reads by extension: `.parquet`,
        `.csv`, `.feather`, or `.sav` if `pyreadstat` is installed.
        """
        spec = load_spec(spec_path)
        return cls(spec, read_table(data_path), verbose=verbose)

    # -- the settings every call shares ------------------------------------

    def _build_kwargs(self, variant_name: str, **overrides: Any) -> dict[str, Any]:
        """Every `build_bn` argument this variant implies, from the spec.

        Collecting them in one place is the point of this class: the layer
        role patterns in particular are easy to omit at a call site, and
        omitting them silently falls back to matching the layer names
        against the strings "Outcomes" and "Dropout".
        """
        variant = self.spec.variant(variant_name)
        constraints = self.spec.constraints
        kwargs: dict[str, Any] = {
            "score": self.spec.model.score,
            "use_tabu": self.spec.model.use_tabu,
            "max_indegree": self.spec.model.max_indegree,
            "exclude_layers": list(variant.exclude_layers),
            "outcome_patterns": self.spec.outcome_patterns,
            "dropout_patterns": self.spec.dropout_patterns,
            # From `constraints` in the spec. Omitting these would silently
            # fall back to the built-in conventions, which is exactly the
            # failure this class exists to prevent.
            "within_layers": constraints.within_layers,
            "arcs_between_outcomes": constraints.arcs_between_outcomes,
            "selection_parents": constraints.selection_parents,
            "forbidden_pairs": self.spec.forbidden_pairs,
            "mandatory_pairs": self.spec.mandatory_pairs,
            "no_parents": constraints.no_parents,
            "no_children": constraints.no_children,
        }
        kwargs.update(overrides)
        return kwargs

    def _reduced_frame(self, variant_name: str) -> pd.DataFrame:
        """The columns `build_bn` will actually learn on, for this variant.

        Mirrors the reduction inside `build_bn`, but uses the spec's layer
        roles rather than the default name patterns, so it is correct
        whatever a cohort calls its layers.
        """
        variant = self.spec.variant(variant_name)
        excluded = [
            v for layer in variant.exclude_layers
            for v in self.spec.layer_map.get(layer, [])
        ]
        outcome_layer_vars = [
            v for layer in self.spec.layers
            if layer.role in ("outcome", "selection")
            for v in layer.variables
        ]
        unused_outcomes = [v for v in outcome_layer_vars if v not in variant.outcomes]
        return self.df.drop(columns=unused_outcomes + excluded, errors="ignore")

    def template(self, variant_name: str) -> Any:
        """The discretisation template for a variant, computed once.

        Sharing one template across bootstrap resamples keeps the bin edges
        fixed, so a state label means the same thing in every resample.
        """
        if variant_name not in self._templates:
            self._templates[variant_name] = self.type_processor.discretizedTemplate(
                self._reduced_frame(variant_name)
            )
        return self._templates[variant_name]

    def bins(self, variant_name: str | None = None) -> pd.DataFrame:
        """The state labels each variable was discretised into.

        Worth reading before interpreting anything else: every result is
        conditional on these bin edges.
        """
        variant_name = variant_name or self.spec.variants[0].name
        return describe_template(self.template(variant_name))

    # -- structure ---------------------------------------------------------

    def network(self, variant_name: str, *, refresh: bool = False, **overrides: Any) -> Any:
        """Learn (and cache) the network for one variant of the spec.

        Parameters
        ----------
        variant_name : str
            A `name` from the spec's `variants` list.
        refresh : bool
            Relearn even if the network is already cached.
        **overrides
            Passed to `build_bn`, replacing the spec's value. Use sparingly:
            a result produced with an override is not described by the spec.
        """
        if refresh or variant_name not in self._networks or overrides:
            variant = self.spec.variant(variant_name)
            bn = build_bn(
                self.df,
                outcomes=list(variant.outcomes),
                layer_map=self.spec.layer_map,
                type_processor=self.type_processor,
                random_seed=self.spec.model.seed,
                fixed_template=self.template(variant_name),
                **self._build_kwargs(variant_name, **overrides),
            )
            if overrides:
                return bn
            self._networks[variant_name] = bn
        return self._networks[variant_name]

    def edge_frequencies(
        self,
        variant_name: str,
        *,
        refresh: bool = False,
        **overrides: Any,
    ) -> dict[tuple[str, str], float]:
        """Bootstrap arc stability: the fraction of resamples containing each arc.

        This is the expensive step. The result is cached per variant, so
        asking for it again — for a table and then for a figure — costs
        nothing. Pass `refresh=True` to recompute.
        """
        if not refresh and not overrides and variant_name in self._edge_freqs:
            return self._edge_freqs[variant_name]

        variant = self.spec.variant(variant_name)
        n = self.spec.bootstrap_for(variant_name)
        progress = _Progress(n, f"edge stability [{variant_name}]", enabled=self.verbose)
        try:
            result = bootstrap_edge_frequencies(
                self.df,
                outcomes=list(variant.outcomes),
                layer_map=self.spec.layer_map,
                type_processor=self.type_processor,
                build_bn_func=progress.wrap(build_bn),
                n_bootstraps=n,
                random_seed=self.spec.model.seed,
                fixed_template=self.template(variant_name),
                **self._build_kwargs(variant_name, **overrides),
            )
        finally:
            progress.finish()
        if not overrides:
            self._edge_freqs[variant_name] = result
        return result

    def stable_edges(
        self,
        variant_name: str,
        *,
        min_frequency: float = 0.0,
        **overrides: Any,
    ) -> pd.DataFrame:
        """Arc stability as a sorted table, ready to report.

        Columns: `Parent`, `Child`, `Frequency`, `In network`. `In network`
        says whether the arc is in the network learned from the full data,
        which is not the same question as how often it survives resampling.

        Parameters
        ----------
        min_frequency : float
            Drop arcs appearing in a smaller fraction of resamples. There is
            no principled threshold; 0.5 and 0.8 are both defensible and both
            arbitrary, so report the frequency rather than only the survivors.
        """
        frequencies = self.edge_frequencies(variant_name, **overrides)
        bn = self.network(variant_name)
        in_network = {
            (bn.variable(p).name(), bn.variable(c).name()) for p, c in bn.arcs()
        }
        rows = [
            {
                "Parent": parent,
                "Child": child,
                "Frequency": frequency,
                "In network": (parent, child) in in_network,
            }
            for (parent, child), frequency in frequencies.items()
            if frequency >= min_frequency
        ]
        table = pd.DataFrame(rows, columns=["Parent", "Child", "Frequency", "In network"])
        return table.sort_values("Frequency", ascending=False).reset_index(drop=True)

    # -- interpretation ----------------------------------------------------

    def information(self, variant_name: str, *, targets: Sequence[str] | None = None) -> pd.DataFrame:
        """Rank variables by mutual information with each spec target.

        Returns one row per (target, variable), with columns:

        `MI`
            Mutual information with the target. How much the variable tells
            you about the outcome on its own.
        `CMI`
            Mutual information given the target's parents in the network.
            What the variable adds *beyond* the variables already adjacent
            to the outcome. A high `MI` with a near-zero `CMI` means the
            variable is explained away by the target's parents.
        `Is parent`
            Whether the variable is itself a parent of the target. `CMI` is
            undefined for those, since they make up the conditioning set,
            so it is left empty rather than reported as zero.

        Values within floating-point noise of zero are rounded to zero;
        mutual information cannot be negative.
        """
        bn = self.network(variant_name)
        targets = list(targets if targets is not None else self.spec.information_targets)
        if not targets:
            raise ValueError(
                "No targets to rank. Add `analyses.information.targets` to the "
                "spec, or pass targets= explicitly."
            )

        frames = []
        for target in targets:
            if target not in bn.names():
                if self.verbose:
                    print(f"  - {target!r} is not in the {variant_name!r} network; skipped.")
                continue
            parents = {
                bn.variable(p).name() for p in bn.parents(bn.idFromName(target))
            }
            mi = mutual_information_scores(bn, target)
            cmi = conditional_mutual_information_scores(bn, target)
            frame = pd.DataFrame({"MI": mi, "CMI": cmi})
            # Both quantities are non-negative; anything below this is the
            # accumulated error of summing over the joint distribution.
            frame = frame.mask(frame.abs() < 1e-12, 0.0)
            frame.insert(0, "Target", target)
            frame.insert(1, "Variable", frame.index)
            frame["Is parent"] = frame["Variable"].isin(parents)
            frames.append(frame.reset_index(drop=True))

        if not frames:
            return pd.DataFrame(
                columns=["Target", "Variable", "MI", "CMI", "Is parent"]
            )
        return (pd.concat(frames, ignore_index=True)
                .sort_values(["Target", "MI"], ascending=[True, False])
                .reset_index(drop=True))

    # -- evidence ----------------------------------------------------------

    def resolve_profile(
        self,
        variant_name: str,
        profile: Mapping[str, Any],
        *,
        label: str = "profile",
    ) -> dict[str, int]:
        """Turn a spec profile into state indices the inference engine accepts.

        `AGE: 72`, `AGE: "72"` and `AGE: 72.0` all resolve to the bin holding
        the age 72. Values that cannot be matched are reported and omitted
        rather than silently discarding the whole profile.
        """
        bn = self.network(variant_name)
        applied: dict[str, int] = {}
        snapped: list[str] = []
        rejected: list[str] = []

        for variable, value in profile.items():
            if variable not in bn.names():
                rejected.append(
                    f"{variable}={value!r} (not a variable in the "
                    f"{variant_name!r} network — excluded by a layer, or misspelt)"
                )
                continue
            labels = list(bn.variable(bn.idFromName(variable)).labels())
            state = state_for_value(labels, value)
            if state is None:
                rejected.append(
                    f"{variable}={value!r} (no matching state; states are {labels})"
                )
                continue
            applied[variable] = labels.index(state)
            if str(value) != state:
                snapped.append(f"{variable}: {value!r} -> {state}")

        if self.verbose:
            if snapped:
                print(f"  {label} — snapped to bins: " + "; ".join(snapped))
            if rejected:
                print(f"  {label} — NOT APPLIED: " + "; ".join(rejected))
        return applied

    def scenarios(self, variant_name: str, **overrides: Any) -> pd.DataFrame:
        """Posterior outcome probabilities for the spec's profiles, with CIs.

        One row per (profile, outcome, outcome state) with the bootstrap mean
        and a 95% percentile interval. The interval covers uncertainty in the
        structure and the parameters, because each resample relearns both.
        """
        scenarios = self.spec.scenarios
        if not scenarios.profiles:
            raise ValueError(
                "No profiles to evaluate. Add `analyses.scenarios.profiles` to the spec."
            )
        if not scenarios.targets:
            raise ValueError(
                "No outcomes to report. Add `analyses.scenarios.targets` to the spec."
            )

        variant = self.spec.variant(variant_name)
        n = scenarios.bootstrap_n or self.spec.bootstrap_for(variant_name)
        resolved = [
            (name, self.resolve_profile(variant_name, evidence, label=name))
            for name, evidence in scenarios.profiles
        ]
        empty = [name for name, evidence in resolved if not evidence]
        if empty:
            raise ValueError(
                f"No evidence could be applied for profile(s) {empty}. "
                "Check the variable names and values against `study.bins()`."
            )

        progress = _Progress(n, f"scenarios [{variant_name}]", enabled=self.verbose)
        try:
            result = bootstrap_scenario_risks(
                self.df,
                scenario_profiles=resolved,
                target_outcomes=list(scenarios.targets),
                layer_map=self.spec.layer_map,
                type_processor=self.type_processor,
                outcomes_for_learning=list(variant.outcomes),
                build_bn_func=progress.wrap(build_bn),
                n_bootstraps=n,
                random_seed=self.spec.model.seed,
                fixed_template=self.template(variant_name),
                **self._build_kwargs(variant_name, **overrides),
            )
        finally:
            progress.finish()
        return result

    def knob_sweep(
        self,
        variant_name: str,
        **overrides: Any,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Vary one variable across its states, holding a profile fixed.

        Returns `(table, meta)`; pass both to `plot_sweep`. Warns when the
        fixed profile includes a variable downstream of the swept one, which
        blocks part of the effect being measured.
        """
        sweep = self.spec.knob_sweep
        if not sweep.knob:
            raise ValueError(
                "No sweep declared. Add `analyses.knob_sweep` to the spec."
            )

        variant = self.spec.variant(variant_name)
        n = sweep.bootstrap_n or self.spec.bootstrap_for(variant_name)
        progress = _Progress(n, f"sweep [{sweep.knob}]", enabled=self.verbose)
        try:
            result = bootstrap_knob_sweep(
                self.df,
                base_profile=dict(sweep.base_profile),
                knob=sweep.knob,
                outcomes=list(sweep.outcomes),
                outcomes_for_learning=list(variant.outcomes),
                layer_map=self.spec.layer_map,
                type_processor=self.type_processor,
                build_bn_func=progress.wrap(build_bn),
                n_bootstraps=n,
                random_seed=self.spec.model.seed,
                verbose=self.verbose,
                **self._build_kwargs(variant_name, **overrides),
            )
        finally:
            progress.finish()
        return result

    # -- figures -----------------------------------------------------------

    def node_colors(self, variant_name: str) -> dict[str, float]:
        """Colour value per variable, one shade per layer, in spec order."""
        return build_node_colors(
            self.network(variant_name),
            self.spec.layer_map,
            default_layer_colors(self.spec.layer_order),
        )

    def arc_widths(
        self,
        variant_name: str,
        *,
        scale: float = 3.0,
        floor: float = 0.5,
    ) -> dict[tuple[int, int], float]:
        """Line width per arc, on the square root of its mutual information.

        Keyed by node id, which is what pyAgrum's renderer expects. The
        square root compresses the range so that one dominant arc does not
        render every other arc as a hairline.
        """
        import pyagrum as gum

        bn = self.network(variant_name)
        engine = gum.LazyPropagation(bn)
        engine.makeInference()

        raw: dict[tuple[int, int], float] = {}
        for parent, child in bn.arcs():
            try:
                info = gum.InformationTheory(engine, child, [parent])
                raw[(parent, child)] = max(info.mutualInformationXY(), 0.0)
            except Exception:
                raw[(parent, child)] = 0.1

        largest = max(raw.values(), default=0.0)
        if largest <= 0:
            return {arc: floor + scale / 2 for arc in raw}
        return {
            arc: float(np.sqrt(value) / np.sqrt(largest) * scale + floor)
            for arc, value in raw.items()
        }

    def draw(
        self,
        variant_name: str,
        *,
        stability: bool = False,
        save_path: str | Path | None = None,
        **kwargs: Any,
    ) -> Any:
        """Draw the network, coloured by layer, optionally writing a file.

        Parameters
        ----------
        stability : bool
            Also encode the bootstrap results: arc width from mutual
            information, arc colour and an `f=NN%` label from the fraction
            of resamples containing the arc. This calls `edge_frequencies`,
            so the first use is slow and later ones are cached.
        save_path : path, optional
            Write the figure as well as displaying it. The format follows
            the extension; use `.pdf` for a figure you intend to edit.
        **kwargs
            Passed to pyAgrum's renderer (`size`, `cmapNode`, `cmapArc`,
            ...), overriding anything set here.
        """
        from pyagrum.lib import notebook as gnb

        bn = self.network(variant_name)
        options: dict[str, Any] = {"nodeColor": self.node_colors(variant_name)}

        if stability:
            frequencies = self.edge_frequencies(variant_name)
            names = set(bn.names())
            by_id = {
                (bn.idFromName(parent), bn.idFromName(child)): frequency
                for (parent, child), frequency in frequencies.items()
                if parent in names and child in names
            }
            options["arcWidth"] = self.arc_widths(variant_name)
            options["arcColor"] = {arc: by_id.get(arc, 0.0) for arc in bn.arcs()}
            options["arcLabel"] = {
                arc: f"f={round(by_id.get(arc, 0.0) * 100)}%" for arc in bn.arcs()
            }

        options.update(kwargs)

        if save_path is not None:
            from pyagrum.lib import image as gumimage
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            gumimage.export(bn, str(save_path), **options)
            if self.verbose:
                print(f"Saved {save_path}")
        return gnb.showBN(bn, **options)

    @staticmethod
    def plot_sweep(table: pd.DataFrame, meta: dict[str, Any]) -> None:
        """Plot the output of `knob_sweep`."""
        plot_knob_sweep(table, meta)

    # -- reporting ---------------------------------------------------------

    def summary(self) -> str:
        """A plain-text description of what the spec declares."""
        lines = [
            f"Spec:      {self.spec.name}  ({self.spec.source})",
            f"Data:      {len(self.df)} rows x {len(self.df.columns)} columns",
            f"Layers:    {len(self.spec.layers)}, in this order (arcs run downwards)",
        ]
        for i, layer in enumerate(self.spec.layers):
            role = "" if layer.role == "covariate" else f"  [{layer.role}]"
            lines.append(f"             {i}. {layer.name}{role}")
            lines.append(f"                {', '.join(layer.variables)}")
        lines += [
            f"Bins:      {self.spec.discretisation.n_bins} "
            f"{self.spec.discretisation.method} bins for numeric variables "
            f"with more than {self.spec.discretisation.threshold} distinct values",
            f"Learner:   {self.spec.model.score}, "
            f"{'tabu search' if self.spec.model.use_tabu else 'greedy hill climbing'}, "
            f"max {self.spec.model.max_indegree} parents per variable, "
            f"seed {self.spec.model.seed}",
            f"Bootstrap: {self.spec.bootstrap_n} resamples",
            "Variants:",
        ]
        for variant in self.spec.variants:
            excluded = (f", excluding {list(variant.exclude_layers)}"
                        if variant.exclude_layers else "")
            lines.append(f"             {variant.name}: "
                         f"outcomes {list(variant.outcomes)}{excluded}")

        constraints = self.spec.constraints
        lines.append("Arcs:")
        lines.append("             only downstream through the layer order above")
        lines.append(f"             within a layer: "
                     f"{'allowed' if constraints.within_layers else 'forbidden'}")
        lines.append(f"             between outcomes: "
                     f"{'allowed' if constraints.arcs_between_outcomes else 'forbidden'}")
        if self.spec.layers_with_role("selection"):
            lines.append(f"             into the selection layer: from "
                         f"{constraints.selection_parents}")
        for label, pairs in (("forbidden", self.spec.forbidden_pairs),
                             ("required", self.spec.mandatory_pairs)):
            if pairs:
                lines.append(f"             {label} ({len(pairs)}):")
                lines += [f"               {p} -> {c}" for p, c in sorted(pairs)]
        if constraints.no_parents:
            lines.append(f"             no parents: {list(constraints.no_parents)}")
        if constraints.no_children:
            lines.append(f"             no children: {list(constraints.no_children)}")
        if self.data_warnings:
            lines.append("Warnings:")
            lines += [f"             - {w}" for w in self.data_warnings]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (f"<Analysis spec={self.spec.name!r} rows={len(self.df)} "
                f"variants={[v.name for v in self.spec.variants]}>")


# ---------------------------------------------------------------------------
# data loading
# ---------------------------------------------------------------------------

_READERS = {
    ".parquet": "read_parquet",
    ".csv": "read_csv",
    ".tsv": "read_csv",
    ".feather": "read_feather",
    ".sav": "read_spss",
    ".dta": "read_stata",
    ".xlsx": "read_excel",
}


def read_table(path: str | Path) -> pd.DataFrame:
    """Read a dataframe, choosing the reader from the file extension."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"data file not found: {path}\n"
            "`data.path` in the spec is resolved relative to the working "
            "directory unless you pass an absolute path."
        )
    reader = _READERS.get(path.suffix.lower())
    if reader is None:
        raise ValueError(
            f"do not know how to read {path.suffix!r}. "
            f"Supported: {sorted(_READERS)}"
        )
    kwargs = {"sep": "\t"} if path.suffix.lower() == ".tsv" else {}
    return getattr(pd, reader)(path, **kwargs)
