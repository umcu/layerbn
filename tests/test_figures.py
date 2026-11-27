"""Figures: they draw, they save, and the network figure keeps its promises."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402

from layerbn import figures  # noqa: E402
from layerbn.figures import FigArc, FigLayer, FigNode  # noqa: E402


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


def test_the_network_figure_draws(study):
    fig = figures.network_figure(study, "all_variables")
    width, height = fig.get_size_inches()
    assert width > 8 and height > 3


def test_the_network_figure_works_without_stability(study):
    fig = figures.network_figure(study, "all_variables", stability=False)
    assert fig is not None


def test_a_variable_can_be_highlighted(study):
    fig = figures.network_figure(study, "all_variables", highlight=["Outcome at follow-up"])
    assert fig is not None


def test_the_design_figure_draws_without_arcs(project):
    fig = figures.design_figure(project)
    assert fig is not None


def test_layers_are_grouped_by_time_point_in_the_grid_layout(write_tables):
    from layerbn.design import load_design
    design = load_design(write_tables(
        "variable,layer\nAGE,Background\nSCORE,Scores\nSTATUS,Status\nOUT,Outcome",
        "layer,repeated\nBackground,no\nScores,yes\nStatus,yes\nOutcome,no",
        "time,label\nT0,First visit\nT1,Second visit"))
    layers = figures.layers_for(design)
    columns = figures._columns(layers, "grid")
    names = [[layer.name for layer in column] for column in columns]
    assert names[0] == ["Background"]
    assert names[1] == ["Scores (First visit)", "Status (First visit)"]
    assert names[2] == ["Scores (Second visit)", "Status (Second visit)"]
    assert names[-1] == ["Outcome"]
    assert len(figures._columns(layers, "columns")) == len(layers)
    assert figures.design_figure is not None


def test_an_arc_that_skips_a_column_is_routed_around_the_boxes():
    layers = [FigLayer(name, name, None, "#2a78d6", tuple(
        FigNode(f"{name}{i}", f"{name} {i}", f"{name} {i}") for i in range(3)))
        for name in ("A", "B", "C")]
    fig = figures.plot_network(layers, [FigArc("A1", "C1", 0.3, 0.8)], legend=False)
    patch = next(p for p in fig.axes[0].patches if type(p).__name__ == "FancyArrowPatch")
    # The middle box of column B is exactly on the straight line from A1 to C1,
    # so the route must leave that line to pass it.
    ys = patch.get_path().vertices[:, 1]
    assert ys.max() - ys.min() > figures.NODE_H / 2


def test_every_arc_gets_its_percentage_by_default():
    layers, arcs = _toy()
    fig = figures.plot_network(layers, arcs)
    texts = {t.get_text() for t in fig.axes[0].texts}
    assert {"90%", "30%"} <= texts


def _toy():
    layers = [
        FigLayer("A", "A", None, "#2a78d6", (FigNode("a1", "A one", "A one"),
                                              FigNode("a2", "A two", "A two"))),
        FigLayer("B", "B", None, "#eb6834", (FigNode("b1", "B one", "B one", True),)),
    ]
    arcs = [FigArc("a1", "b1", 0.4, 0.9), FigArc("a2", "b1", 0.1, 0.3),
            FigArc("a1", "ghost", 0.1, 0.5)]            # an unknown variable is skipped
    return layers, arcs


def test_the_layout_can_be_forced_and_unknown_arcs_are_skipped():
    layers, arcs = _toy()
    for layout in ("columns", "grid", "auto"):
        assert figures.plot_network(layers, arcs, layout=layout) is not None


def test_the_figure_scales_with_the_number_of_layers():
    layers, arcs = _toy()
    small = figures.plot_network(layers[:1], [], legend=False).get_size_inches()[0]
    large = figures.plot_network(layers, arcs).get_size_inches()[0]
    assert large > small


def test_a_layer_with_many_variables_is_split_into_columns():
    nodes = tuple(FigNode(f"v{i}", f"Item {i}", f"Item {i}") for i in range(23))
    layers = [FigLayer("Items", "Items", None, "#2a78d6", nodes),
              FigLayer("Out", "Out", None, "#eb6834", (FigNode("o", "Outcome", "Outcome"),))]
    fig = figures.plot_network(layers, [FigArc("v0", "o", None, None)])
    assert fig.get_size_inches()[1] < 12, "23 items should not make one very tall column"


def test_arc_colour_runs_from_light_to_dark():
    def lightness(hex_colour):
        return sum(int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    assert lightness(figures.arc_colour(0.0)) > lightness(figures.arc_colour(0.5)) \
        > lightness(figures.arc_colour(1.0))
    assert figures.arc_colour(None) == figures.arc_colour(float("nan"))


def test_the_other_figures_draw(study):
    stability = study.stable_edges("all_variables")
    importance = study.importance("all_variables")
    profiles = study.profiles()
    sweep, meta = study.sweep()
    drawn = [
        figures.plot_stability(stability),
        figures.plot_importance(importance, "Dependent on care"),
        figures.plot_profiles(profiles),
        figures.plot_sweep(sweep, meta),
        figures.plot_comparison(study.compare_networks()),
        figures.plot_bins(study.df, study.design, study.template("all_variables")),
    ]
    assert all(fig is not None for fig in drawn)


def test_an_empty_stability_table_does_not_crash(study):
    empty = study.stable_edges("all_variables").iloc[0:0]
    assert figures.plot_stability(empty) is not None


def test_figures_are_saved_as_png_and_pdf(tmp_path, project):
    fig = figures.design_figure(project)
    written = figures.save_figure(fig, tmp_path / "out" / "design")
    assert sorted(p.suffix for p in written) == [".pdf", ".png"]
    assert all(p.stat().st_size > 1000 for p in written)
    # An extension in the name is accepted and not doubled.
    again = figures.save_figure(fig, tmp_path / "x.png", formats=("png",))
    assert again[0].name == "x.png"


def test_pdf_text_stays_editable(tmp_path):
    layers, arcs = _toy()
    written = figures.save_figure(figures.plot_network(layers, arcs), tmp_path / "n",
                                  formats=("pdf",))
    # With fonttype 42 the text is embedded as a font and not as outlines.
    assert b"/FontFile" in written[0].read_bytes()


def test_wrapping_never_returns_more_lines_than_allowed():
    text = figures._wrap("a very long label " * 10, 20, 3)
    assert text.count("\n") == 2 and text.endswith("…")
