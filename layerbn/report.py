"""The HTML report.

One self-contained file: figures are embedded, so the report can be e-mailed
or archived without the folder beside it. It has the same content as the
tables and figures in the results folder, in reading order, with a short
note on how to read each part, a methods paragraph that can be adapted for a
manuscript, and what is needed to reproduce the run.
"""
from __future__ import annotations

import base64
import html
import platform
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from layerbn.analysis import Analysis
    from layerbn.runner import RunResult

CSS = """
:root { --ink:#1f2328; --ink2:#57606a; --ink3:#8c959f; --line:#e6e8eb; --tint:#f6f8fa; --accent:#2166ac; }
* { box-sizing: border-box; }
body { margin:0; background:#fff; color:var(--ink); line-height:1.55;
  font:15px/1.55 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
main { max-width:1120px; margin:0 auto; padding:36px 28px 80px; }
h1 { font-size:26px; margin:0 0 6px; }
h2 { font-size:20px; margin:48px 0 8px; padding-top:18px; border-top:1px solid var(--line); }
h3 { font-size:16px; margin:30px 0 6px; }
p { margin:8px 0; max-width:78ch; }
.sub { color:var(--ink2); margin:0 0 18px; }
.meta { color:var(--ink2); font-size:13px; }
.how { background:var(--tint); border-left:3px solid var(--accent); padding:8px 14px;
  color:var(--ink2); font-size:13.5px; margin:10px 0 16px; max-width:90ch; }
.warn { background:#fdf1ec; border-left:3px solid #b2182b; padding:8px 14px; font-size:13.5px;
  margin:10px 0; max-width:90ch; }
.facts { display:flex; flex-wrap:wrap; gap:12px; margin:18px 0 6px; }
.fact { border:1px solid var(--line); border-radius:8px; padding:10px 16px; min-width:140px; }
.fact b { display:block; font-size:22px; line-height:1.2; }
.fact span { color:var(--ink2); font-size:12.5px; }
figure { margin:14px 0 22px; }
figure img { max-width:100%; height:auto; border:1px solid var(--line); border-radius:6px; }
figure.wide { overflow-x:auto; }
figure.wide img { min-width:1000px; max-width:none; width:100%; }
figcaption { color:var(--ink2); font-size:13px; margin-top:4px; max-width:90ch; }
table { border-collapse:collapse; font-size:13px; margin:8px 0 18px; }
th, td { padding:5px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
th { background:var(--tint); font-weight:600; position:sticky; top:0; }
td.num { text-align:right; font-variant-numeric:tabular-nums; }
.scroll { max-height:520px; overflow:auto; border:1px solid var(--line); border-radius:6px; display:inline-block; max-width:100%; }
details { margin:8px 0 18px; }
summary { cursor:pointer; color:var(--accent); }
code, pre { font:12.5px ui-monospace, Menlo, Consolas, monospace; background:var(--tint); }
pre { padding:12px 14px; overflow-x:auto; border-radius:6px; white-space:pre-wrap; }
nav { font-size:13.5px; margin:12px 0 0; }
nav a { margin-right:16px; color:var(--accent); text-decoration:none; }
"""


# ---------------------------------------------------------------------------
# small pieces
# ---------------------------------------------------------------------------

def _e(text: Any) -> str:
    return html.escape(str(text))


def _image(path: Path, alt: str, caption: str = "", *, wide: bool = False) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    cls = ' class="wide"' if wide else ""
    cap = f"<figcaption>{caption}</figcaption>" if caption else ""
    return (f'<figure{cls}><img alt="{_e(alt)}" src="data:image/png;base64,{data}">'
            f"{cap}</figure>")


def _table(frame: pd.DataFrame, formats: dict[str, Any] | None = None, *,
           scroll: bool = False, max_rows: int | None = None) -> str:
    formats = formats or {}
    shown = frame.head(max_rows) if max_rows else frame
    head = "".join(f"<th>{_e(c)}</th>" for c in shown.columns)
    rows = []
    for _, row in shown.iterrows():
        cells = []
        for column, value in row.items():
            numeric = isinstance(value, (int, float, np.integer, np.floating)) \
                and not isinstance(value, bool)
            if column in formats and not (isinstance(value, float) and np.isnan(value)):
                text = formats[column](value)
            elif isinstance(value, float) and np.isnan(value):
                text = ""
            elif isinstance(value, (bool, np.bool_)):
                text = "yes" if value else "no"
            else:
                text = value
            cells.append(f'<td class="{"num" if numeric else ""}">{_e(text)}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    table = f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    if max_rows and len(frame) > max_rows:
        table += f'<p class="meta">Showing {max_rows} of {len(frame)} rows. All rows are in the CSV file.</p>'
    return f'<div class="scroll">{table}</div>' if scroll else table


def _pct(value: float) -> str:
    return f"{value:.0%}"


def _bits(value: float) -> str:
    return f"{value:.3f}"


def _how(text: str) -> str:
    return f'<div class="how">{text}</div>'


def _warn(text: str) -> str:
    return f'<div class="warn">{text}</div>'


def _versions() -> dict[str, str]:
    import matplotlib
    import pyagrum
    import sklearn

    import layerbn
    return {
        "layerbn": layerbn.__version__, "Python": platform.python_version(),
        "pyAgrum": pyagrum.__version__, "pandas": pd.__version__,
        "numpy": np.__version__, "scikit-learn": sklearn.__version__,
        "matplotlib": matplotlib.__version__,
        "Platform": f"{platform.system()} {platform.release()}",
    }


# ---------------------------------------------------------------------------
# methods text
# ---------------------------------------------------------------------------

def methods_text(study: Analysis, run: RunResult) -> str:
    """A methods paragraph describing what was done, for adaptation in a paper."""
    s, p, d = study.project.settings, study.project, study.design
    versions = _versions()
    n_layers = len(d.layers)
    score = {"K2": "the K2 score", "BIC": "the BIC score",
             "BDEU": "the BDeu score"}[s.learning.score]
    search = ("a tabu search" if s.learning.search == "tabu"
              else "greedy hill climbing")
    binned = [v for v in study.bins()["Treated as"] if v.startswith("continuous")]

    parts = [
        f"Bayesian networks were learned from {study.n} participants with pyAgrum "
        f"{versions['pyAgrum']}, using {search} and {score}, with at most "
        f"{s.learning.max_parents} parents per variable (random seed {s.learning.seed}). "
        f"Continuous variables ({len(binned)} of {len(d.variables)}) were discretised "
        f"into {s.discretisation.bins} {s.discretisation.method}-based bins; variables "
        f"with at most {s.discretisation.categorical_max_levels} distinct values were "
        "used as categories",
    ]
    overrides = [v for v in d.variables if v.bins or v.cutpoints or v.kind]
    parts[0] += (f", except {len(overrides)} variable(s) with their own setting in the "
                 "design table." if overrides else ".")

    within_off = [layer.name for layer in d.layers if not p.arcs_within(layer.name)]
    structure = (
        f"The {len(d.variables)} variables were arranged in {n_layers} ordered layers "
        "based on prior knowledge of the order of influence"
        + (" and of the time of measurement" if d.timepoints else "")
        + ". Arcs were only allowed from a layer to itself or to a later layer"
        + (f", and not within {', '.join(within_off)}" if within_off else "") + ".")
    if p.forbidden_pairs or p.mandatory_pairs or p.no_parents or p.no_children:
        extra = []
        if p.forbidden_pairs:
            extra.append(f"{len(p.forbidden_pairs)} arc(s) were forbidden")
        if p.mandatory_pairs:
            extra.append(f"{len(p.mandatory_pairs)} arc(s) were required")
        if p.no_parents:
            extra.append(f"{len(p.no_parents)} variable(s) were allowed no parents")
        if p.no_children:
            extra.append(f"{len(p.no_children)} variable(s) were allowed no children")
        structure += " In addition, " + "; ".join(extra) + "."
    parts.append(structure)

    counts = sorted({n.resamples for n in p.networks})
    parts.append(
        "The stability of each arc was assessed by learning the network, including "
        "its structure, on "
        + (f"{counts[0]}" if len(counts) == 1 else f"{counts[0]} to {counts[-1]}")
        + " bootstrap resamples of the participants (sampling with replacement, "
        "same bins in every resample) and recording the proportion of resamples "
        "that contained the arc. The strength of an arc was expressed as the mutual "
        "information (in bits) between its two variables in the fitted network. "
        "The importance of each variable for a target was expressed as its mutual "
        "information with the target, together with its relation to the target in "
        "the learned structure.")
    if p.profile_groups:
        parts.append(
            "Probabilities of the targets for defined profiles were obtained by "
            "entering the profile values as evidence in each bootstrap network; "
            "the reported interval is the 2.5th to 97.5th percentile over resamples.")
    parts.append("These are conditional probabilities in the learned distribution; the "
                 "arcs describe the assumed order of variables and associations "
                 "that are supported by the data, not established causal effects.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------

def render_report(study: Analysis, run: RunResult) -> str:
    """Build the HTML report for a finished run."""
    p, s, d = study.project, study.project.settings, study.design
    out: list[str] = []
    started: datetime = run.started

    # -- header ---------------------------------------------------------------
    sections = ["Design", "Data and bins"] + [f"Network: {n}" for n in run.networks]
    if run.profiles is not None:
        sections.append("Profiles")
    if run.sweep is not None:
        sections.append("Sweep")
    if run.comparison is not None:
        sections.append("Comparison")
    sections += ["Methods", "Reproducibility"]
    nav = "".join(f'<a href="#{_slug(x)}">{_e(x)}</a>' for x in sections)

    out.append(f"<h1>{_e(s.name)}</h1>")
    if s.description:
        out.append(f'<p class="sub">{_e(s.description)}</p>')
    out.append(f'<p class="meta">Created {started:%d %B %Y, %H:%M} with layerbn '
               f"{_versions()['layerbn']}.</p><nav>{nav}</nav>")

    if run.fast:
        out.append(_warn(
            "<b>Trial run.</b> The number of bootstrap resamples was reduced to "
            f"{p.networks[0].resamples} to save time. Arc stability and intervals are "
            "imprecise. Do not report these numbers. Run again without <code>--fast</code>."))

    first = next(iter(run.networks.values()))
    stable = int((first.stability["Frequency"] >= 0.8).sum())
    out.append('<div class="facts">'
               f'<div class="fact"><b>{study.n}</b><span>participants</span></div>'
               f'<div class="fact"><b>{len(d.variables)}</b><span>variables</span></div>'
               f'<div class="fact"><b>{len(d.layers)}</b><span>layers</span></div>'
               f'<div class="fact"><b>{len(run.networks)}</b><span>network(s)</span></div>'
               f'<div class="fact"><b>{first.n_arcs}</b><span>arcs in "{_e(first.name)}"</span></div>'
               f'<div class="fact"><b>{stable}</b><span>arcs in at least 80% of resamples ("{_e(first.name)}")</span></div>'
               "</div>")

    # -- notes ---------------------------------------------------------------------
    if study.notes or run.notes:
        items = "".join(f"<li>{_e(n)}</li>" for n in [*study.notes, *run.notes])
        out.append(_warn(f"<b>Notes on this run</b><ul>{items}</ul>"))

    # -- design --------------------------------------------------------------------
    out.append(f'<h2 id="{_slug("Design")}">Design</h2>')
    out.append(_how(
        "Variables are grouped in layers. The order of the layers is the assumed order "
        "of influence. Arcs may only run from a layer to itself or to a later layer. "
        "Read the figure from the top down: the first layer is the top row. "
        "A layer's colour shows its place in the order, from blue (first) to red (last). "
        "A target variable has a solid title strip."))
    out.append(_image(run.figures["design"], "Layers and variables", wide=True))
    out.append("<details><summary>Variable table</summary>"
               + _table(d.table(), scroll=True) + "</details>")

    # -- data ------------------------------------------------------------------------
    out.append(f'<h2 id="{_slug("Data and bins")}">Data and bins</h2>')
    out.append(_how(
        "The network works on discrete variables, so continuous variables are cut into "
        "bins. <b>All results depend on these bins.</b> Check that the bin edges (black "
        "lines) are sensible, that no bin holds very few participants, and that variables "
        "that should have been kept as categories were not binned."))
    out.append(_image(run.figures["bins"], "Distributions and bin edges"))
    out.append(_table(run.bins, scroll=True))

    # -- networks --------------------------------------------------------------------
    for name, result in run.networks.items():
        out.append(f'<h2 id="{_slug(f"Network: {name}")}">Network: {_e(name)}</h2>')
        if result.description:
            out.append(f"<p>{_e(result.description)}</p>")
        out.append(_how(
            "<b>Arc darkness and the percentage</b> show how often the arc appears when the "
            "network is learned again on resampled data (arc stability). <b>Arc width</b> is "
            "the mutual information between the two variables. A wide, light arc is "
            "informative but unstable. A dashed arc occurred in fewer than half of the "
            "resamples. There is no fixed threshold for a stable arc: report the "
            "frequency."))
        out.append(_image(result.figures["network"], f"Network {name}", wide=True))
        out.append("<h3>Arc stability</h3>")
        out.append(_how(
            "<b>In network</b> says whether the arc is in the single network learned from "
            "all data. This is a different question from stability, and the two can "
            "disagree in both directions."))
        out.append(_image(result.figures["stability"], f"Arc stability {name}"))
        out.append("<details><summary>All arcs (table)</summary>"
                   + _table(result.stability, {"Frequency": _pct,
                                               "Mutual information (bits)": _bits},
                            scroll=True) + "</details>")
        if result.importance is not None and len(result.importance):
            out.append("<h3>Variables ranked by information about each target</h3>")
            out.append(_how(
                "Mutual information (bits) is how much a variable tells about the target. "
                "It includes information passed on through other variables, so a variable can "
                "rank high without being directly connected to the target. The colour shows "
                "the relation in the learned structure. This is an association, not an "
                "effect estimate."))
            for target, path in result.figures_importance.items():
                out.append(_image(path, f"Importance for {target}"))
            out.append("<details><summary>Table</summary>"
                       + _table(result.importance, {"Mutual information (bits)": _bits},
                                scroll=True) + "</details>")

    # -- profiles --------------------------------------------------------------------
    if run.profiles is not None:
        out.append(f'<h2 id="{_slug("Profiles")}">Profiles</h2>')
        out.append(_how(
            "Probability of each target state for the profiles defined in the settings "
            "(network: <code>" + _e(p.profile_network) + "</code>). The point is the mean over "
            "bootstrap resamples and the line is the 95% percentile interval. Each resample "
            "learns the structure and the parameters again, so the interval includes both "
            "sources of uncertainty. Values given for a profile were placed in the bin they "
            "belong to; see the notes above."))
        out.append(_image(run.figures["profiles"], "Profiles"))
        out.append(_table(run.profiles, {"Probability": _pct, "SD": _pct,
                                         "CI 2.5%": _pct, "CI 97.5%": _pct},
                          scroll=True))

    if run.sweep is not None:
        table, meta = run.sweep
        out.append(f'<h2 id="{_slug("Sweep")}">Sweep: {_e(meta["variable"])}</h2>')
        out.append(_how(
            "One variable is moved across its states while the rest of the profile is held "
            "fixed. A rising or falling line means the target probability depends on that "
            "variable in the learned distribution. A flat line can also arise if a variable "
            "between the moved variable and the target is held fixed. These are conditional "
            "probabilities. They describe people who differ in the variable, not the effect "
            "of changing it in one person."))
        out.append(_image(run.figures["sweep"], "Sweep"))
        out.append("<details><summary>Table</summary>"
                   + _table(table, {"probability": _pct, "ci_low": _pct, "ci_high": _pct},
                            scroll=True) + "</details>")

    if run.comparison is not None:
        out.append(f'<h2 id="{_slug("Comparison")}">Comparison of networks</h2>')
        out.append(_how(
            "Arc stability in each network. A dash means the arc did not occur in any "
            "resample of that network, or the arc is not possible there. Use this to see what "
            "changes when a layer or a variable is left out."))
        out.append(_image(run.figures["comparison"], "Network comparison"))

    # -- methods and reproducibility --------------------------------------------------
    out.append(f'<h2 id="{_slug("Methods")}">Methods</h2>')
    out.append("<p>A description of what was done, based on the settings of this run. "
               "Adapt it for a manuscript and check it against your own choices.</p>")
    out.append(f"<p>{_e(methods_text(study, run))}</p>")

    out.append(f'<h2 id="{_slug("Reproducibility")}">Reproducibility</h2>')
    settings_rows = pd.DataFrame([
        ("Score / search", f"{s.learning.score} / {s.learning.search}"),
        ("Maximum parents", s.learning.max_parents),
        ("Random seed", s.learning.seed),
        ("Binning", f"{s.discretisation.bins} {s.discretisation.method} bins; "
                    f"categories up to {s.discretisation.categorical_max_levels} levels"),
        ("Bootstrap resamples", ", ".join(f"{n.name}: {n.resamples}" for n in p.networks)),
        ("Missing data", s.data.missing),
        ("Forbidden arcs", len(p.forbidden_pairs)),
        ("Required arcs", len(p.mandatory_pairs)),
    ], columns=["Setting", "Value"])
    out.append(_table(settings_rows))
    files = pd.DataFrame([(k, v["name"], v["sha256"], v["info"])
                          for k, v in run.inputs.items()],
                         columns=["File", "Name", "SHA-256 (first 16)", "Content"])
    out.append(_table(files))
    versions = pd.DataFrame(list(_versions().items()), columns=["Software", "Version"])
    out.append(_table(versions))
    out.append("<p class=\"meta\">The settings and the design table used are copied to the "
               "<code>inputs</code> folder next to this report.</p>")

    body = "\n".join(out)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{_e(s.name)}: layerbn report</title><style>{CSS}</style></head>"
            f"<body><main>{body}</main></body></html>")


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")
