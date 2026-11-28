"""Draw the layerbn logo.

    python docs/assets/build_logo.py

writes, next to this file:

    logo.svg / logo.png            full logo for light backgrounds
    logo-dark.svg / logo-dark.png  the same for dark backgrounds
    mark.svg / mark.png            the symbol alone, square

The symbol is the method in miniature: variables in ordered layers, with arcs
that only run forward. The layers take colours along ColorBrewer RdBu, blue
first and red last, exactly as in the figures, so the logo and the output look
like one product. Text is converted to outlines in the
SVG, so it displays the same on every computer.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

HERE = Path(__file__).parent

THEMES = {
    "light": {
        "ink": "#1f2328", "ink2": "#57606a", "arc": "#b9c2cc", "arc_strong": "#4a5868",
        "layers": ["#2166ac", "#7db8d7", "#ec9374", "#b2182b"],
        "accent": "#2166ac", "node_edge": "#ffffff",
    },
    "dark": {
        "ink": "#eef1f4", "ink2": "#a9b3be", "arc": "#4a5563", "arc_strong": "#aab5c1",
        "layers": ["#4393c3", "#92c5de", "#f4a582", "#d6604d"],
        "accent": "#92c5de", "node_edge": "#0d1117",
    },
}

FONT_CHOICES = ["Avenir Next", "Helvetica Neue", "DejaVu Sans"]

# Positions in logo units: 940 wide, 300 high (100 units = 1 inch).
COLUMNS_X = [62, 142, 222, 302]
NODES = [
    [(62, 100), (62, 200)],
    [(142, 62), (142, 150), (142, 238)],
    [(222, 100), (222, 200)],
    [(302, 150)],
]
# (from column, from node, to column, to node, strong)
ARCS = [
    (0, 0, 1, 0, False), (0, 0, 1, 1, True), (0, 1, 1, 1, False), (0, 1, 1, 2, True),
    (1, 0, 2, 0, True), (1, 1, 2, 0, False), (1, 1, 2, 1, True), (1, 2, 2, 1, False),
    (2, 0, 3, 0, True), (2, 1, 3, 0, True),
]


def _pick_font() -> str:
    from matplotlib import font_manager as fm
    available = {f.name for f in fm.fontManager.ttflist}
    return next((f for f in FONT_CHOICES if f in available), "DejaVu Sans")


def draw_mark(ax, theme: dict, *, dx: float = 0.0, dy: float = 0.0) -> None:
    """The symbol, with its left edge at `dx`: coloured nodes and thin arcs."""
    for c0, n0, c1, n1, strong in ARCS:
        (x0, y0), (x1, y1) = NODES[c0][n0], NODES[c1][n1]
        x0, x1, y0, y1 = x0 + dx, x1 + dx, y0 + dy, y1 + dy
        reach = (x1 - x0) * 0.5
        path = MPath([(x0, y0), (x0 + reach, y0), (x1 - reach, y1), (x1, y1)],
                     [MPath.MOVETO, MPath.CURVE4, MPath.CURVE4, MPath.CURVE4])
        ax.add_patch(PathPatch(
            path, facecolor="none", linewidth=3.0 if strong else 1.8, zorder=2,
            edgecolor=theme["arc_strong"] if strong else theme["arc"], capstyle="round"))

    for column, nodes, colour in zip(COLUMNS_X, NODES, theme["layers"], strict=True):
        for x, y in nodes:
            last = column == COLUMNS_X[-1]
            radius = 19 if last else 13
            ax.add_patch(plt.Circle((x + dx, y + dy), radius, facecolor=colour,
                                    edgecolor=theme["node_edge"], linewidth=3.0, zorder=3))


def build(name: str, theme: dict, *, mark_only: bool = False) -> None:
    font = _pick_font()
    plt.rcParams.update({"svg.fonttype": "path", "font.family": font})

    if mark_only:
        fig = plt.figure(figsize=(3.4, 3.1))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 340)
        ax.set_ylim(310, 0)
        ax.axis("off")
        draw_mark(ax, theme, dx=-14, dy=5)
    else:
        fig = plt.figure(figsize=(9.4, 3.0))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 940)
        ax.set_ylim(300, 0)
        ax.axis("off")
        draw_mark(ax, theme, dx=10)
        # "layer" in ink and "bn" in the blue of the first layer, side by side.
        x0, y0, size = 396, 126, 80
        word = ax.text(x0, y0, "layer", fontsize=size, fontweight="bold",
                       color=theme["ink"], ha="left", va="center")
        fig.canvas.draw()
        box = word.get_window_extent(fig.canvas.get_renderer())
        x_bn = x0 + box.width / fig.dpi * 100        # pixels to logo units (10 in = 1000)
        ax.text(x_bn, y0, "bn", fontsize=size, fontweight="bold",
                color=theme["accent"], ha="left", va="center")
        ax.text(x0 + 4, 212, "Layered Bayesian networks for cohort studies", fontsize=17,
                fontweight="normal", color=theme["ink2"], ha="left", va="center")

    for ext in ("svg", "png"):
        fig.savefig(HERE / f"{name}.{ext}", dpi=300, transparent=True)
    plt.close(fig)


if __name__ == "__main__":
    build("logo", THEMES["light"])
    build("logo-dark", THEMES["dark"])
    build("mark", THEMES["light"], mark_only=True)
    print("wrote", ", ".join(sorted(p.name for p in HERE.glob("logo*")) +
                              sorted(p.name for p in HERE.glob("mark*"))))
