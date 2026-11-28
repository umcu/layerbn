"""Figures.

All figures are drawn with matplotlib, with no other graphics program needed.
Each function takes plain data (tables and small dataclasses) and returns a
matplotlib `Figure`; `save_figure` writes PNG (for slides and documents) and
PDF (vector, with editable text) side by side.

Conventions, in every figure:

* One palette, ColorBrewer **RdBu**. Layers take colours along it in causal
  order, from blue (first) to red (last), the same at every time point.
  **Arc stability** runs along the blue side of the palette, light to dark.
  Layers are also named directly on the figure, so nothing depends on colour
  alone.
* Text is always in the ink colours; colour is carried by marks.
* The network is read from the top down: the first layer is the top row and
  the outcome the bottom row. An arc never points upwards.

The network figure
------------------
Each layer is a row, named in the left margin beside a rule in its colour.
Each variable is a card with its name in a strip tinted in the layer colour
and its marginal distribution in the fitted network as one bar per state.
With repeated measures each time point is headed in the margin, and the same
variable keeps the same horizontal position at every time point.

* arc **width**: mutual information between parent and child, in bits
* arc **darkness**: share of bootstrap resamples that contain the arc
* **dashed** arc: in fewer than half of the resamples
* **percentage** beside each arc: the same share
* **solid title strip**: a target

Arcs that skip a row are routed through the gaps between cards, arcs inside a
row arch above it, and the arcs at one edge of a card are spread along it, so
no arc runs behind a card and no two arcs end in one point.
"""
from __future__ import annotations

import math
import textwrap
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# style
# ---------------------------------------------------------------------------

INK = "#1f2328"
INK_2 = "#57606a"
INK_3 = "#8c959f"
GRID = "#e6e8eb"
SURFACE = "#ffffff"

# One palette throughout: ColorBrewer RdBu, from dark red to dark blue. Layers
# take colours along it in causal order (see `layerbn.design.layer_colours`);
# series in the charts alternate between its blue and red sides, strongest
# first.
RDBU = ("#67001f", "#b2182b", "#d6604d", "#f4a582", "#fddbc7", "#f7f7f7",
        "#d1e5f0", "#92c5de", "#4393c3", "#2166ac", "#053061")
SERIES = ("#2166ac", "#b2182b", "#4393c3", "#d6604d",
          "#053061", "#67001f", "#92c5de", "#f4a582")

# Arc stability: the blue side of RdBu, from light blue (rarely found) to the
# palette's darkest blue (found in every resample).
_ARC_LOW = (0xb4, 0xd4, 0xe8)
_ARC_HIGH = (0x05, 0x30, 0x61)

STYLE = {
    "font.family": "sans-serif",
    # Arial is on Windows and macOS and has a true bold. DejaVu Sans ships with
    # matplotlib, so figures still draw, and look the same, on any computer.
    "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 9,
    "text.color": INK,
    "axes.edgecolor": INK_3,
    "axes.labelcolor": INK_2,
    "axes.titlecolor": INK,
    "xtick.color": INK_2,
    "ytick.color": INK_2,
    "axes.facecolor": SURFACE,
    "figure.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.8,
    "pdf.fonttype": 42,     # keep text as text, so it can be edited in Illustrator
    "svg.fonttype": "none",
}


def _rc():
    import matplotlib.pyplot as plt
    return plt.rc_context(STYLE)


def _mix(hex_colour: str, other: str, share: float) -> str:
    """`share` of `other` mixed into `hex_colour`."""
    from matplotlib.colors import to_rgb
    a, b = np.array(to_rgb(hex_colour)), np.array(to_rgb(other))
    out = a * (1 - share) + b * share
    return "#" + "".join(f"{round(c * 255):02x}" for c in out)


def arc_colour(frequency: float | None) -> str:
    """Grey for an arc, darker the more resamples contain it."""
    if frequency is None or np.isnan(frequency):
        return "#56606d"
    f = min(max(float(frequency), 0.0), 1.0)
    rgb = [round(lo + (hi - lo) * f) for lo, hi in zip(_ARC_LOW, _ARC_HIGH, strict=True)]
    return "#" + "".join(f"{c:02x}" for c in rgb)


def _heading(fig: Any, title: str, subtitle: str | None = None) -> float:
    """Title and subtitle at the top left, placed in inches so they never overlap.

    Returns the height in inches that the heading uses, for `tight_layout`.
    """
    height = fig.get_figheight()
    fig.text(0.01, 1 - 0.28 / height, title, fontsize=12, fontweight="bold",
             ha="left", va="center")
    used = 0.55
    if subtitle:
        fig.text(0.01, 1 - 0.58 / height, subtitle, fontsize=8.3, color=INK_2,
                 ha="left", va="center")
        used = 0.85
    return used


def _wrap(text: str, width: int, lines: int) -> str:
    parts = textwrap.wrap(str(text), width=width, break_long_words=True) or [""]
    if len(parts) > lines:
        parts = parts[:lines]
        parts[-1] = parts[-1][: max(width - 1, 1)].rstrip() + "…"
    return "\n".join(parts)


def save_figure(fig: Any, path: str | Path, formats: Sequence[str] = ("png", "pdf"),
                dpi: int = 300) -> list[Path]:
    """Write a figure in several formats. `path` may omit the extension."""
    path = Path(path)
    if path.suffix.lower().lstrip(".") in ("png", "pdf", "svg"):
        path = path.with_suffix("")
    path.parent.mkdir(parents=True, exist_ok=True)
    written = []
    # The style is applied again here: matplotlib reads the font settings for
    # PDF and SVG when the file is written, not when the figure is drawn.
    with _rc():
        for fmt in formats:
            target = path.with_suffix(f".{fmt}")
            fig.savefig(target, dpi=dpi, bbox_inches="tight", pad_inches=0.15)
            written.append(target)
    return written


# ---------------------------------------------------------------------------
# data for the network figure
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FigNode:
    column: str
    label: str                     # full label
    short: str                     # without the time point
    is_target: bool = False
    states: tuple[str, ...] = ()   # readable states, drawn as bars when probs are given
    probs: tuple[float, ...] = ()  # marginal probability of each state


@dataclass(frozen=True)
class FigLayer:
    name: str
    title: str
    time: str | None
    colour: str
    nodes: tuple[FigNode, ...]


@dataclass(frozen=True)
class FigArc:
    parent: str
    child: str
    strength: float | None = None      # mutual information, bits
    frequency: float | None = None     # share of bootstrap resamples


@dataclass
class _Box:
    node: FigNode
    layer: FigLayer
    x: float = 0.0
    y: float = 0.0
    col: int = 0                   # the visual row it is in
    top: float = 0.0
    bottom: float = 0.0


# ---------------------------------------------------------------------------
# the network figure
# ---------------------------------------------------------------------------

CARD_W = 2.10             # width of a variable card
HEAD_H = 0.30             # its title strip
STATE_H = 0.150           # one line per state
CARD_PAD = 0.10           # space under the last state
GAP_X = 0.42              # between two cards in a row
ROW_GAP = 0.95            # between two rows: arcs and percentages live here
SUB_GAP = 0.30            # between the sub-rows of a long layer
GUTTER = 1.75             # left margin with the layer names
MAX_PER_ROW = 6


def _columns(layers: Sequence[FigLayer], layout: str) -> list[list[FigLayer]]:
    """Group layers by time point. Used to head each time point in the figure."""
    if layout == "columns":
        return [[layer] for layer in layers]
    columns: list[list[FigLayer]] = []
    for layer in layers:
        if columns and layer.time is not None and columns[-1][-1].time == layer.time:
            columns[-1].append(layer)
        else:
            columns.append([layer])
    return columns


def _luminance(hex_colour: str) -> float:
    from matplotlib.colors import to_rgb
    r, g, b = to_rgb(hex_colour)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _card_height(node: FigNode) -> float:
    if not node.states:
        return HEAD_H
    return HEAD_H + len(node.states) * STATE_H + CARD_PAD


def _clip(text: str, n: int) -> str:
    text = str(text)
    return text if len(text) <= n else text[: max(n - 1, 1)].rstrip() + "…"


def plot_network(
    layers: Sequence[FigLayer],
    arcs: Sequence[FigArc],
    *,
    title: str | None = None,
    subtitle: str | None = None,
    layout: str = "auto",
    highlight: Sequence[str] = (),
    label_below: float | None = None,
    max_arc_labels: int = 60,
    legend: bool = True,
) -> Any:
    """Draw layers and arcs, from the top down.

    Each layer is a row, in causal order from top to bottom, named in the left
    margin beside a rule in its colour. Each variable is a card: its name in a
    strip tinted in the layer's colour (solid for a target) and, when the
    node has `states` and `probs`, one bar per state with its probability.
    Arcs run downwards, darker and wider the more stable and informative,
    each with its percentage beside it.

    Arcs that skip a row are routed through the gaps between the cards of the
    rows they cross, so they never run behind a variable, and the arcs at one
    edge of a card are spread along it. Each percentage sits on its own arc,
    at a place where it covers no card, no other percentage and as few other
    arcs as possible.

    Parameters
    ----------
    layers, arcs
        What to draw. An arc's `strength` sets its width and its `frequency`
        its colour; either may be `None`.
    layout : {"auto", "columns", "grid"}
        With `grid` (the default when layers have time points) each time
        point is headed in the margin; otherwise the time point is part of
        the layer name.
    highlight : sequence of column names
        Draw only the arcs that touch these variables at full strength and
        fade the others. Useful for reading the neighbourhood of a target.
    label_below
        By default every arc with a known frequency has its percentage
        written on it. With a value, only arcs below it are labelled. At most
        `max_arc_labels` arcs are labelled, the least stable first.
    """
    import matplotlib.pyplot as plt
    from matplotlib import patheffects
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle
    from matplotlib.path import Path as MPath

    if layout == "auto":
        layout = "grid" if any(layer.time for layer in layers) else "columns"
    groups = _columns(layers, layout)
    first_of_time = {group[0].name for group in groups if group[0].time} \
        if layout == "grid" else set()

    # ---- geometry (inches; y grows downwards) ----------------------------------
    left = 0.40
    top_margin = 1.05 if (title or subtitle) else 0.35
    # Visual rows: a layer is one row, or several sub-rows when it is long.
    rows: list[dict[str, Any]] = []
    for layer in layers:
        nodes = list(layer.nodes)
        chunks = [nodes[i:i + MAX_PER_ROW] for i in range(0, len(nodes), MAX_PER_ROW)] or [[]]
        for j, chunk in enumerate(chunks):
            rows.append({"layer": layer, "nodes": chunk, "first": j == 0,
                         "last": j == len(chunks) - 1,
                         "height": max((_card_height(n) for n in chunk), default=HEAD_H)})
    # A layer with arcs inside it gets more room above it, for their arches.
    layer_of = {n.column: layer.name for layer in layers for n in layer.nodes}
    inner = {layer_of[a.parent] for a in arcs
             if a.parent in layer_of and layer_of.get(a.child) == layer_of[a.parent]}
    widest = max((len(r["nodes"]) for r in rows), default=1)
    content_w = widest * CARD_W + (widest - 1) * GAP_X
    x_content = left + GUTTER

    boxes: dict[str, _Box] = {}
    y = top_margin
    layer_span: dict[str, list[float]] = {}
    for i, row in enumerate(rows):
        gap = 0.0
        if i:
            # Without arcs (the design figure) the rows can sit closer.
            gap = (ROW_GAP if arcs else 0.42) if row["first"] else SUB_GAP
        if row["first"] and row["layer"].name in inner:
            gap += 0.55
        y += gap
        row["gap"] = gap
        if row["layer"].name in first_of_time:
            y += 0.22                                      # room for the time heading
        row["top"], row["bottom"] = y, y + row["height"]
        k = len(row["nodes"])
        x0 = x_content + (content_w - (k * CARD_W + (k - 1) * GAP_X)) / 2
        for j, node in enumerate(row["nodes"]):
            cx = x0 + CARD_W / 2 + j * (CARD_W + GAP_X)
            box = _Box(node, row["layer"], cx, y + _card_height(node) / 2, i)
            box.top, box.bottom = y, y + _card_height(node)
            boxes[node.column] = box
        span = layer_span.setdefault(row["layer"].name, [y, y])
        span[1] = y + row["height"]
        y += row["height"]
    bottom = y

    width_in = x_content + content_w + 0.45
    legend_h = 1.0 if legend else 0.3
    height_in = bottom + legend_h

    with _rc():
        fig = plt.figure(figsize=(width_in, height_in))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, width_in)
        ax.set_ylim(height_in, 0)
        ax.axis("off")

        if title:
            ax.text(left, 0.34, title, fontsize=13, fontweight="bold", va="center",
                    color=INK)
        if subtitle:
            ax.text(left, 0.66, subtitle, fontsize=8.4, color=INK_2, va="center")

        # layer names in the margin, beside a rule in the layer's colour
        for layer in layers:
            y0, y1 = layer_span[layer.name]
            if layer.name in first_of_time:
                ax.text(left, y0 - 0.16, str(layer.time).upper(), fontsize=7.6,
                        fontweight="bold", color=INK_3, va="center")
            heading = layer.title if layout == "grid" else (
                f"{layer.title} · {layer.time}" if layer.time else layer.title)
            ax.plot([left, left], [y0 + 0.02, y1 - 0.02], color=layer.colour, lw=3.0,
                    solid_capstyle="round", zorder=1)
            ax.text(left + 0.14, y0 + 0.12, _wrap(heading, 20, 3), fontsize=8.6,
                    fontweight="bold", color=INK, va="top", ha="left", zorder=1,
                    linespacing=1.15)

        # ---- arcs ---------------------------------------------------------------
        highlight_set = set(highlight)
        strengths = [a.strength for a in arcs if a.strength is not None
                     and np.isfinite(a.strength)]
        top = max(strengths, default=0.0)

        def width_of(arc: FigArc) -> float:
            if arc.strength is None or not np.isfinite(arc.strength) or top <= 0:
                return 1.2
            return 0.6 + 1.9 * math.sqrt(arc.strength / top)

        def faded(arc: FigArc) -> bool:
            return bool(highlight_set) and not ({arc.parent, arc.child} & highlight_set)

        ordered = sorted(
            (a for a in arcs if a.parent in boxes and a.child in boxes),
            key=lambda a: (not faded(a), -1 if a.frequency is None else a.frequency))
        label_candidates = sorted(
            (a for a in ordered if a.frequency is not None and not faded(a)
             and (label_below is None or a.frequency < label_below)),
            key=lambda a: a.frequency)[:max_arc_labels]
        labelled = {(a.parent, a.child) for a in label_candidates}

        def same_row(arc: FigArc) -> bool:
            return boxes[arc.parent].col == boxes[arc.child].col

        # Free horizontal corridors in each row, for arcs that pass through it.
        x_low, x_high = x_content - 0.35, x_content + content_w + 0.35
        blocked: dict[int, list[tuple[float, float]]] = {i: [] for i in range(len(rows))}
        for box in boxes.values():
            blocked[box.col].append((box.x - CARD_W / 2 - 0.05, box.x + CARD_W / 2 + 0.05))

        def corridors(k: int) -> list[tuple[float, float]]:
            free, x = [], x_low
            for lo, hi in sorted(blocked[k]):
                if lo > x:
                    free.append((x, lo))
                x = max(x, hi)
            if x < x_high:
                free.append((x, x_high))
            return free or [(x_low, x_high)]

        corridor_use: dict[tuple[int, float], int] = {}

        def s_curve(a, b):
            reach = max(0.16, 0.45 * abs(b[1] - a[1]))
            return (a, (a[0], a[1] + reach), (b[0], b[1] - reach), b)

        # Ports: the arcs at one edge of a card are spread along it, ordered by
        # where their other end is, so they do not meet in one point.
        def edges(arc: FigArc) -> tuple[str, str]:
            # Inside one row an arc leaves and enters through the top edges and
            # arches through the open space above the row, so it never crosses
            # a card in between.
            return ("top", "top") if same_row(arc) else ("bottom", "top")

        at_edge: dict[tuple[str, str], list[tuple[float, tuple[str, str], str]]] = {}
        for arc in ordered:
            out_edge, in_edge = edges(arc)
            key = (arc.parent, arc.child)
            at_edge.setdefault((arc.parent, out_edge), []).append(
                (boxes[arc.child].x, key, "out"))
            at_edge.setdefault((arc.child, in_edge), []).append(
                (boxes[arc.parent].x, key, "in"))
        port: dict[tuple[tuple[str, str], str], tuple[float, float]] = {}
        for (column, edge), ends in at_edge.items():
            box = boxes[column]
            ends.sort(key=lambda e: e[0])
            n = len(ends)
            step = min(0.20, (CARD_W - 0.6) / max(n - 1, 1))
            y_edge = box.top if edge == "top" else box.bottom
            for i, (_, key, end) in enumerate(ends):
                port[(key, end)] = (box.x + (i - (n - 1) / 2) * step, y_edge)

        def route(arc: FigArc) -> list[tuple]:
            """The arc as a list of cubic Bezier segments."""
            key = (arc.parent, arc.child)
            p, c = boxes[arc.parent], boxes[arc.child]
            p0, p1 = port[(key, "out")], port[(key, "in")]
            if same_row(arc):                       # inside one row: an arch above it
                # Wider arches rise higher, so arches inside one row nest.
                room = rows[p.col]["gap"] or ROW_GAP
                lift = min(0.30 + 0.09 * abs(p1[0] - p0[0]), room * 0.62)
                return [(p0, (p0[0], p0[1] - lift), (p1[0], p1[1] - lift), p1)]
            if c.col - p.col < 2:
                return [s_curve(p0, p1)]
            points = [p0]
            for k in range(p.col + 1, c.col):
                share = ((rows[k]["top"] + rows[k]["bottom"]) / 2 - p0[1]) / (p1[1] - p0[1])
                wanted = p0[0] + (p1[0] - p0[0]) * share
                best = None
                for lo, hi in corridors(k):
                    pad = min(0.10, (hi - lo) / 2)
                    x = min(max(wanted, lo + pad), hi - pad)
                    cost = abs(x - wanted) + (0.3 if hi - lo < 0.15 else 0.0)
                    if best is None or cost < best[0]:
                        best = (cost, x, lo, hi)
                _, x, lo, hi = best
                used = corridor_use.get((k, lo), 0)
                corridor_use[(k, lo)] = used + 1
                if used:
                    step = 0.06 * ((used + 1) // 2) * (1 if used % 2 else -1)
                    x = min(max(x + step, lo + 0.03), hi - 0.03)
                points += [(x, rows[k]["top"] - 0.06), (x, rows[k]["bottom"] + 0.06)]
            points.append(p1)
            segments = []
            for i, (a, b) in enumerate(zip(points, points[1:], strict=False)):
                if i % 2:                                    # straight through a row
                    segments.append((a, (a[0], a[1] + (b[1] - a[1]) / 3),
                                     (b[0], a[1] + 2 * (b[1] - a[1]) / 3), b))
                else:
                    segments.append(s_curve(a, b))
            return segments

        def sample(segments: list[tuple]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            """Points along the arc, their distance from the start, and their segment."""
            ts = np.linspace(0, 1, 60)[:, None]
            pts, seg = [], []
            for i, (a, b, cc, d) in enumerate(segments):
                a, b, cc, d = (np.array(v) for v in (a, b, cc, d))
                pts.append((1 - ts) ** 3 * a + 3 * (1 - ts) ** 2 * ts * b
                           + 3 * (1 - ts) * ts ** 2 * cc + ts ** 3 * d)
                seg.append(np.full(len(ts), i))
            xy = np.vstack(pts)
            dist = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(xy, axis=0).T))])
            return xy, dist, np.concatenate(seg)

        routes = {(a.parent, a.child): route(a) for a in ordered}
        samples = {key: sample(segments) for key, segments in routes.items()}

        for arc in ordered:
            lw = width_of(arc)
            segments = routes[(arc.parent, arc.child)]
            vertices = [segments[0][0]]
            for _, b, cc, d in segments:
                vertices += [b, cc, d]
            path = MPath(vertices, [MPath.MOVETO] + [MPath.CURVE4] * (3 * len(segments)))
            dashed = arc.frequency is not None and arc.frequency < 0.5
            alpha = 0.12 if faded(arc) else 1.0
            ax.add_patch(FancyArrowPatch(
                path=path, arrowstyle="-|>,head_length=0.62,head_width=0.28",
                mutation_scale=5.5 + 1.0 * lw, linewidth=lw,
                color=arc_colour(arc.frequency), alpha=alpha,
                linestyle=(0, (3.2, 2.2)) if dashed else "solid",
                shrinkA=0, shrinkB=0.4, zorder=2, capstyle="round", joinstyle="round"))

        # Percentages: each on its own arc, clear of the cards and each other,
        # over a white halo instead of in a box.
        obstacles = [(b.x - CARD_W / 2 - 0.03, b.top - 0.03, b.x + CARD_W / 2 + 0.03,
                      b.bottom + 0.03) for b in boxes.values()]
        placed: list[tuple[float, float, float, float]] = []
        halo = [patheffects.withStroke(linewidth=3.2, foreground=SURFACE)]

        def overlaps(r, others) -> bool:
            return any(r[0] < o[2] and o[0] < r[2] and r[1] < o[3] and o[1] < r[3]
                       for o in others)

        for arc in sorted((a for a in ordered if (a.parent, a.child) in labelled),
                          key=lambda a: len(routes[(a.parent, a.child)])):
            key = (arc.parent, arc.child)
            xy, dist, seg = samples[key]
            length = dist[-1]
            text = f"{round(arc.frequency * 100)}%"
            half_w, half_h = (0.05 * len(text) + 0.06) / 2, 0.07
            if same_row(arc):
                preferred = length / 2
            else:
                # In the open gap above the child's row.
                idx = np.where(seg == seg.max())[0]
                target_y = xy[-1, 1] - ROW_GAP * 0.42
                preferred = dist[idx[np.argmin(abs(xy[idx, 1] - target_y))]]
            others = [samples[k][0] for k in samples if k != key]
            best = None
            for i in range(len(dist)):
                if dist[i] < min(0.18, length * 0.15) or length - dist[i] < min(0.2, length * 0.2):
                    continue
                x, y = xy[i]
                rect = (x - half_w, y - half_h, x + half_w, y + half_h)
                if overlaps(rect, obstacles) or overlaps(rect, placed):
                    continue
                crossed = sum(bool(np.any((o[:, 0] > rect[0]) & (o[:, 0] < rect[2])
                                          & (o[:, 1] > rect[1]) & (o[:, 1] < rect[3])))
                              for o in others)
                cost = abs(dist[i] - preferred) + 1.0 * crossed
                if best is None or cost < best[0]:
                    best = (cost, x, y, rect)
            if best is None:                                 # crowded: fall back to the middle
                i = int(np.argmin(abs(dist - length / 2)))
                x, y = xy[i]
                best = (0, x, y, (x - half_w, y - half_h, x + half_w, y + half_h))
            _, x, y, rect = best
            placed.append(rect)
            ax.text(x, y, text, fontsize=6.8, color=INK, ha="center", va="center",
                    zorder=4, path_effects=halo)

        # ---- cards ------------------------------------------------------------------
        touched = ({n for a in arcs for n in (a.parent, a.child)
                    if a.parent in highlight_set or a.child in highlight_set}
                   | highlight_set)
        for box in boxes.values():
            node, layer = box.node, box.layer
            dim = bool(highlight_set) and node.column not in touched
            alpha = 0.35 if dim else 1.0
            colour = layer.colour
            h = box.bottom - box.top
            x0 = box.x - CARD_W / 2
            card = FancyBboxPatch(
                (x0, box.top), CARD_W, h, boxstyle="round,pad=0,rounding_size=0.06",
                facecolor=SURFACE, edgecolor=colour if node.is_target else
                _mix(colour, "#ffffff", 0.45),
                linewidth=1.6 if node.is_target else 0.8, alpha=alpha, zorder=3)
            ax.add_patch(card)
            strip = Rectangle((x0, box.top), CARD_W, min(HEAD_H, h),
                              facecolor=colour if node.is_target else
                              _mix(colour, "#ffffff", 0.80),
                              edgecolor="none", alpha=alpha, zorder=3.1)
            ax.add_patch(strip)
            strip.set_clip_path(card)
            head_ink = ("#ffffff" if node.is_target and _luminance(colour) < 0.55 else INK)
            text = node.short if layout == "grid" and layer.time else node.label
            ax.text(x0 + 0.09, box.top + HEAD_H / 2, _clip(text, 34), fontsize=7.4,
                    fontweight="bold", color=head_ink, va="center", ha="left",
                    alpha=alpha, zorder=5)
            if not node.states:
                continue
            bar_x0, bar_x1 = x0 + 0.92, x0 + CARD_W - 0.46
            bar_colour = colour if _luminance(colour) < 0.85 else INK_3
            for k, (state, p) in enumerate(zip(node.states, node.probs, strict=False)):
                yk = box.top + HEAD_H + 0.07 + (k + 0.5) * STATE_H - 0.02
                ax.text(x0 + 0.09, yk, _clip(state, 15), fontsize=6.3, color=INK_2,
                        va="center", ha="left", alpha=alpha, zorder=5)
                ax.add_patch(Rectangle((bar_x0, yk - 0.042), bar_x1 - bar_x0, 0.084,
                                       facecolor=GRID, edgecolor="none", alpha=alpha,
                                       zorder=4))
                if p is not None and np.isfinite(p):
                    ax.add_patch(Rectangle((bar_x0, yk - 0.042),
                                           (bar_x1 - bar_x0) * min(max(p, 0.0), 1.0), 0.084,
                                           facecolor=bar_colour, edgecolor="none",
                                           alpha=alpha, zorder=4.1))
                    ax.text(x0 + CARD_W - 0.08, yk, f"{p:.0%}" if p >= 0.01 or p == 0
                            else "<1%", fontsize=6.3, color=INK, va="center", ha="right",
                            alpha=alpha, zorder=5)

        if legend:
            _draw_network_legend(ax, left, bottom + 0.45, arcs, top, label_below,
                                 target_colour=next((b.layer.colour for b in boxes.values()
                                                     if b.node.is_target), INK))

    return fig


def _draw_network_legend(ax: Any, x0: float, y0: float,
                         arcs: Sequence[FigArc], top_strength: float,
                         label_below: float | None, *, target_colour: str = INK) -> None:
    """One quiet row under the network: stability, information, dashes, target."""
    from matplotlib.patches import FancyBboxPatch, Rectangle

    has_freq = any(a.frequency is not None for a in arcs)
    has_strength = top_strength > 0
    size, colour = 7.2, INK_2
    x = x0
    if has_freq:
        ax.text(x, y0, "Stability: share of bootstrap resamples with the arc",
                fontsize=size, color=colour, va="center")
        steps = 40
        for i in range(steps):
            ax.add_patch(Rectangle((x + i * 0.045, y0 + 0.14), 0.045, 0.07,
                                   facecolor=arc_colour(i / (steps - 1)), edgecolor="none"))
        for share in (0, 0.5, 1.0):
            ax.text(x + share * 1.8, y0 + 0.34, f"{round(share * 100)}%", fontsize=6.6,
                    color=INK_3, ha="center", va="center")
        x += 3.4
    if has_strength:
        ax.text(x, y0, f"Width: mutual information (up to {top_strength:.2f} bits)",
                fontsize=size, color=colour, va="center")
        for i, share in enumerate((0.1, 0.4, 1.0)):
            lw = 0.6 + 1.9 * math.sqrt(share)
            ax.plot([x + i * 0.6, x + i * 0.6 + 0.42], [y0 + 0.18] * 2,
                    color=arc_colour(1.0), lw=lw, solid_capstyle="round")
        x += 3.2
    if has_freq:
        ax.text(x, y0, "Dashed: in fewer than half", fontsize=size, color=colour,
                va="center")
        ax.plot([x, x + 0.6], [y0 + 0.18] * 2, color=arc_colour(0.4), lw=1.2,
                linestyle=(0, (3.2, 2.2)))
        x += 2.2
    ax.text(x, y0, "Solid title: target variable", fontsize=size, color=colour,
            va="center")
    ax.add_patch(FancyBboxPatch((x, y0 + 0.11), 0.5, 0.15,
                                boxstyle="round,pad=0,rounding_size=0.03",
                                facecolor=target_colour, edgecolor="none"))
    if has_freq and label_below is not None:
        ax.text(x0, y0 + 0.56, f"Percentages are written on arcs below {label_below:.0%}.",
                fontsize=6.6, color=INK_3, va="center")


# ---------------------------------------------------------------------------
# simple charts
# ---------------------------------------------------------------------------

def _style_axes(ax: Any, *, grid: str = "x") -> None:
    ax.grid(axis=grid, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=8)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID if side == "left" else INK_3)


def plot_stability(table: pd.DataFrame, *, top: int = 30, title: str | None = None,
                   subtitle: str | None = None) -> Any:
    """Horizontal bars: share of bootstrap resamples containing each arc.

    `table` is the output of `Analysis.stable_edges`.
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    shown = table.head(top).iloc[::-1].reset_index(drop=True)
    n = len(shown)
    with _rc():
        fig, ax = plt.subplots(figsize=(8.6, 1.4 + 0.42 * max(n, 3)))
        if n == 0:
            ax.text(0.5, 0.5, "No arcs", ha="center", transform=ax.transAxes)
            return fig
        colours = [SERIES[0] if inside else _mix(SERIES[0], "#ffffff", 0.62)
                   for inside in shown["In network"]]
        ax.barh(range(n), shown["Frequency"], height=0.58, color=colours, zorder=3)
        ax.axvline(0.5, color=INK_3, lw=0.8, zorder=2)
        for i, f in enumerate(shown["Frequency"]):
            ax.text(min(f + 0.012, 1.0), i, f"{f:.0%}", va="center", fontsize=8, color=INK)
        ax.set_yticks(range(n))
        ax.set_yticklabels([f"{p}\n→ {c}" for p, c in
                            zip(shown["Parent"], shown["Child"], strict=True)],
                           fontsize=7.4, linespacing=1.1)
        ax.set_xlim(0, 1.08)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
        ax.set_xlabel("Share of bootstrap resamples that contain the arc")
        _style_axes(ax)
        ax.legend(handles=[Patch(color=SERIES[0],
                                 label="Arc is in the network learned from all data"),
                           Patch(color=_mix(SERIES[0], "#ffffff", 0.62),
                                 label="Arc is not in that network")],
                  loc="lower right", frameon=False, fontsize=8)
        fig.suptitle(title or "Arc stability", x=0.01, ha="left", fontsize=12,
                     fontweight="bold")
        if subtitle:
            ax.set_title(subtitle, loc="left", fontsize=8.5, color=INK_2, pad=8)
        fig.tight_layout()
    return fig


RELATION_COLOURS = {
    "parent": "#2166ac",
    "child": "#b2182b",
    "co-parent": "#92c5de",
    "other": "#cfd5dc",
}
RELATION_NOTES = {
    "parent": "parent of the target",
    "child": "child of the target",
    "co-parent": "shares a child with the target",
    "other": "not directly connected",
}


def plot_importance(table: pd.DataFrame, target: str, *, top: int = 15,
                    title: str | None = None) -> Any:
    """Mutual information of each variable with one target, coloured by relation.

    `table` is the output of `Analysis.importance`.
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    column = "Mutual information (bits)"
    sub = table[table["Target"] == target].head(top).iloc[::-1].reset_index(drop=True)
    n = len(sub)
    with _rc():
        fig, ax = plt.subplots(figsize=(8.2, 1.4 + 0.36 * max(n, 3)))
        ys = np.arange(n)
        ax.barh(ys, sub[column], height=0.6, zorder=3,
                color=[RELATION_COLOURS[r] for r in sub["Relation"]])
        top_value = max(float(sub[column].max()) if n else 0.0, 1e-9)
        for y, value in zip(ys, sub[column], strict=True):
            ax.text(value + 0.012 * top_value, y, f"{value:.3f}", va="center",
                    fontsize=7.6, color=INK)
        ax.set_yticks(ys)
        ax.set_yticklabels(sub["Variable"], fontsize=8)
        ax.set_xlim(0, top_value * 1.15)
        ax.set_xlabel("Mutual information with the target (bits)")
        _style_axes(ax)
        present = [r for r in RELATION_COLOURS if r in set(sub["Relation"])]
        ax.legend(handles=[Patch(color=RELATION_COLOURS[r], label=RELATION_NOTES[r])
                           for r in present],
                  loc="lower right", frameon=False, fontsize=8)
        ax.set_title(title or f"Information about {target}", loc="left", fontsize=11,
                     fontweight="bold", pad=10)
        fig.tight_layout()
    return fig


def _percent_axis(ax: Any, upper: float) -> None:
    ax.set_xlim(0, min(1.0, upper * 1.15 + 0.02))
    ticks = ax.get_xticks()
    ax.set_xticks([t for t in ticks if 0 <= t <= ax.get_xlim()[1]])
    ax.set_xticklabels([f"{t:.0%}" for t in ax.get_xticks()])


def plot_profiles(table: pd.DataFrame, *, title: str | None = None) -> Any:
    """Probability of each state of each target for each profile, with 95% intervals."""
    import matplotlib.pyplot as plt

    targets = list(dict.fromkeys(table["Target"]))
    profiles = list(dict.fromkeys(table["Profile"]))
    n_prof = len(profiles)
    rows_per = [table[table["Target"] == t]["State"].nunique() for t in targets]
    heights = [0.5 + 0.34 * (n_prof + 0.5) * r for r in rows_per]
    top_in, bottom_in = 0.85, 0.75
    total = sum(heights) + top_in + bottom_in + 0.45 * len(targets)

    with _rc():
        fig, axes = plt.subplots(len(targets), 1, figsize=(8.0, total), squeeze=False,
                                 gridspec_kw={"height_ratios": heights})
        for ax, target in zip(axes[:, 0], targets, strict=True):
            sub = table[table["Target"] == target]
            states = list(dict.fromkeys(sub["State"]))
            step = n_prof + 0.6
            for j, profile in enumerate(profiles):
                rows = sub[sub["Profile"] == profile].set_index("State").reindex(states)
                ys = np.array([k * step + j for k in range(len(states))], float)
                colour = SERIES[j % len(SERIES)]
                ax.hlines(ys, rows["CI 2.5%"], rows["CI 97.5%"], color=colour, lw=2.2,
                          zorder=3)
                ax.plot(rows["Probability"], ys, "o", color=colour, ms=8,
                        markeredgecolor=SURFACE, markeredgewidth=1.6, zorder=4,
                        label=profile, linestyle="none")
                for y, p, hi in zip(ys, rows["Probability"], rows["CI 97.5%"], strict=True):
                    if np.isfinite(p):
                        ax.text(hi + 0.012, y, f"{p:.0%}", fontsize=7.8, ha="left",
                                va="center", color=INK)
            ax.set_yticks([k * step + (n_prof - 1) / 2 for k in range(len(states))])
            ax.set_yticklabels(states, fontsize=8.5)
            ax.set_ylim(len(states) * step - 0.6, -0.8)
            _percent_axis(ax, float(sub["CI 97.5%"].max()) + 0.05)
            ax.set_xlabel("Probability (mean and 95% bootstrap interval)")
            ax.set_title(target, loc="left", fontsize=10, fontweight="bold")
            _style_axes(ax)
        handles, labels = axes[0, 0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower center", ncol=min(len(labels), 3),
                   frameon=False, fontsize=8.5, bbox_to_anchor=(0.5, 0.0))
        _heading(fig, title or "Outcome probabilities by profile",
                 "Point: mean over bootstrap resamples. Line: 95% percentile interval.")
        fig.tight_layout(rect=(0, bottom_in / total, 1, 1 - top_in / total))
    return fig


def plot_sweep(table: pd.DataFrame, meta: Mapping[str, Any], *,
               title: str | None = None) -> Any:
    """Target probabilities across the states of the moved variable."""
    import matplotlib.pyplot as plt

    variable = meta["variable"]
    x_states = meta["variable_states"]
    targets = meta["targets"]
    x = np.arange(len(x_states))
    fixed = ", ".join(f"{k} = {v}" for k, v in meta.get("fixed", {}).items()) or "none"

    with _rc():
        total = 3.7 * len(targets) + 1.2
        fig, axes = plt.subplots(len(targets), 1, figsize=(7.8, total), squeeze=False)
        for ax, target in zip(axes[:, 0], targets, strict=True):
            sub = table[table["target"] == target]
            states = meta["target_states"][target]
            for j, state in enumerate(states):
                d = (sub[sub["target_state"] == state].set_index("variable_state")
                     .reindex(x_states))
                colour = SERIES[j % len(SERIES)]
                ax.fill_between(x, d["ci_low"], d["ci_high"], color=colour, alpha=0.12,
                                linewidth=0)
                ax.plot(x, d["probability"], "-o", color=colour, lw=2.0, ms=7,
                        markeredgecolor=SURFACE, markeredgewidth=1.5, label=state, zorder=3)
                last = d["probability"].iloc[-1]
                if np.isfinite(last):
                    ax.annotate(f"{last:.0%}", (x[-1], last), xytext=(8, 0),
                                textcoords="offset points", va="center", fontsize=8,
                                color=INK)
            ax.set_xticks(x)
            ax.set_xticklabels(x_states, fontsize=8)
            ax.set_xlim(-0.2, len(x) - 1 + 0.45)
            top = float(np.nanmax(sub["ci_high"])) if len(sub) else 1.0
            ax.set_ylim(0, min(1.0, top * 1.12 + 0.02))
            ax.set_yticks([t for t in ax.get_yticks() if 0 <= t <= ax.get_ylim()[1]])
            ax.set_yticklabels([f"{t:.0%}" for t in ax.get_yticks()])
            ax.set_xlabel(variable)
            ax.set_ylabel("Probability")
            ax.set_title(target, loc="left", fontsize=10, fontweight="bold")
            ax.legend(frameon=False, fontsize=8, title=None, loc="best")
            _style_axes(ax, grid="y")
        _heading(fig, title or f"Probability of the targets across {variable}",
                 f"Held fixed: {fixed}. Line: mean over resamples. Band: 95% bootstrap interval.")
        fig.tight_layout(rect=(0, 0, 1, 1 - 0.95 / total))
    return fig


def plot_comparison(table: pd.DataFrame, *, top: int = 25,
                    title: str | None = None) -> Any:
    """Arc frequency in each network, as a matrix."""
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    names = [c for c in table.columns if c not in ("Parent", "Child")]
    shown = table.head(top).reset_index(drop=True)
    n = len(shown)
    cmap = LinearSegmentedColormap.from_list(
        "stability", [arc_colour(0.0), arc_colour(1.0)])
    with _rc():
        fig, ax = plt.subplots(figsize=(1.8 + 1.3 * len(names) + 4.0, 1.2 + 0.4 * max(n, 3)))
        values = shown[names].to_numpy(float)
        for i in range(n):
            for j in range(len(names)):
                v = values[i, j]
                if np.isnan(v):
                    ax.text(j, i, "–", ha="center", va="center", color=INK_3, fontsize=9)
                    continue
                ax.add_patch(plt.Rectangle((j - 0.46, i - 0.42), 0.92, 0.84,
                                           color=cmap(v), zorder=2))
                ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=8,
                        color="white" if v > 0.45 else INK, zorder=3)
        ax.set_xlim(-0.6, len(names) - 0.4)
        ax.set_ylim(n - 0.5, -0.5)
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, fontsize=8.5)
        ax.xaxis.tick_top()
        ax.set_yticks(range(n))
        ax.set_yticklabels([f"{p} → {c}" for p, c in
                            zip(shown["Parent"], shown["Child"], strict=True)], fontsize=7.4)
        ax.tick_params(length=0)
        for side in ("left", "bottom", "top"):
            ax.spines[side].set_visible(False)
        fig.suptitle(title or "Arc stability in each network", x=0.01, ha="left",
                     fontsize=12, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.95))
    return fig


# ---------------------------------------------------------------------------
# bins
# ---------------------------------------------------------------------------

def plot_bins(df: pd.DataFrame, design: Any, template: Any, *, ncols: int = 4,
              title: str | None = None) -> Any:
    """Distribution of every variable with its bin edges.

    Continuous variables are shown as histograms with a line at each bin edge;
    categorical variables as bars. Look at this before interpreting results:
    a bin edge that cuts through a dense part of the distribution, or bins
    with very few participants, will limit what the network can find.
    """
    import matplotlib.pyplot as plt

    from layerbn.discretisation import _bounds

    names = [name for _, name in template]
    n = len(names)
    nrows = math.ceil(n / ncols)
    with _rc():
        fig, axes = plt.subplots(nrows, ncols, figsize=(3.2 * ncols, 2.15 * nrows + 0.7),
                                 squeeze=False)
        for ax in axes.ravel()[n:]:
            ax.axis("off")
        for ax, (i, column) in zip(axes.ravel(), template, strict=False):
            labels = list(template.variable(i).labels())
            series = df[column]
            colour = design.layer(design.variable(column).layer).colour
            edges_ = [_bounds(lab) for lab in labels]
            if all(e is not None for e in edges_):
                ax.hist(series, bins=30, color=_mix(colour, "#ffffff", 0.25), zorder=3)
                cuts = sorted({e[1] for e in edges_} | {e[0] for e in edges_})[1:-1]
                for cut in cuts:
                    ax.axvline(cut, color=INK, lw=1.0, zorder=4)
                ax.set_yticks([])
                ax.spines["left"].set_visible(False)
            else:
                counts = series.astype(str).value_counts().reindex(labels).fillna(0)
                ax.bar(range(len(labels)), counts.values, color=_mix(colour, "#ffffff", 0.25),
                       width=0.6, zorder=3)
                ax.set_xticks(range(len(labels)))
                ax.set_xticklabels([_wrap(lab, 9, 2) for lab in labels], fontsize=6.5)
                ax.set_yticks([])
                ax.spines["left"].set_visible(False)
            ax.set_title(_wrap(design.label(column), 38, 2), loc="left", fontsize=7.8,
                         fontweight="bold")
            ax.tick_params(length=0, labelsize=7)
            ax.set_axisbelow(True)
        fig.suptitle(title or "Distribution of the variables and their bin edges",
                     x=0.01, ha="left", fontsize=12, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.96))
    return fig


# ---------------------------------------------------------------------------
# building figures from a project / analysis
# ---------------------------------------------------------------------------

def layers_for(design: Any, columns: Sequence[str] | None = None,
               layer_map: Mapping[str, Sequence[str]] | None = None) -> list[FigLayer]:
    """Figure layers from a design, optionally restricted to some columns."""
    keep = set(columns) if columns is not None else None
    result = []
    for layer in design.layers:
        if layer_map is not None and layer.name not in layer_map:
            continue
        nodes = tuple(
            FigNode(column=c, label=design.variable(c).label,
                    short=design.variable(c).short_label,
                    is_target=design.variable(c).target)
            for c in layer.variables if keep is None or c in keep)
        if nodes:
            result.append(FigLayer(name=layer.name, title=layer.title, time=layer.time,
                                   colour=layer.colour, nodes=nodes))
    return result


def network_marginals(study: Any, network: str | None = None
                      ) -> dict[str, tuple[tuple[str, ...], tuple[float, ...]]]:
    """`{column: (readable states, probabilities)}` in the fitted network.

    The marginal distribution implied by the network, by exact inference
    without evidence: what each card of the network figure shows.
    """
    import pyagrum as gum

    name = study.project.network(network).name
    bn = study.network(name)
    engine = gum.LazyPropagation(bn)
    engine.makeInference()
    result = {}
    for column in bn.names():
        labels = list(bn.variable(column).labels())
        pretty = study._states(name, column)
        result[column] = (tuple(pretty.get(s, s) for s in labels),
                          tuple(float(v) for v in engine.posterior(column).toarray()))
    return result


def network_figure(study: Any, network: str | None = None, *, stability: bool = True,
                   highlight: Sequence[str] = (), layout: str = "auto",
                   title: str | None = None) -> Any:
    """The network figure for one network of an `Analysis`.

    With `stability=True` the arc colour shows the bootstrap frequency, which
    runs the bootstrap for this network if that has not been done yet.
    """
    definition = study.project.network(network)
    columns = list(definition.columns)
    layers = layers_for(study.design, columns, definition.layer_map)
    targets = set(study.project.default_targets(definition))
    marginals = network_marginals(study, definition.name)
    layers = [FigLayer(layer.name, layer.title, layer.time, layer.colour, tuple(
        FigNode(n.column, n.label, n.short, n.column in targets,
                *marginals.get(n.column, ((), ())))
        for n in layer.nodes))
        for layer in layers]

    strengths = study.arc_strengths(definition.name)
    frequencies = study.edge_frequencies(definition.name) if stability else {}
    arcs = [FigArc(p, c, strengths.get((p, c)), frequencies.get((p, c)) if stability else None)
            for p, c in study.arcs(definition.name)]

    subtitle = (f"Network '{definition.name}': {len(columns)} variables, {len(arcs)} arcs, "
                f"{study.n} participants")
    if stability:
        subtitle += f", {definition.resamples} bootstrap resamples"
    return plot_network(
        layers, arcs, title=title or study.project.name, subtitle=subtitle,
        highlight=[study.design.resolve_variable(h) for h in highlight], layout=layout)


def design_figure(project: Any, *, layout: str = "auto") -> Any:
    """The layers and variables without arcs, to check the design before running."""
    design = project.design
    layers = layers_for(design)
    n = len(design.variables)
    return plot_network(
        layers, [], title=f"{project.name}: layers and variables",
        subtitle=(f"{n} variables in {len(layers)} layers. Arcs may only run from a layer "
                  "to itself or to a layer further down."),
        layout=layout, legend=False)
