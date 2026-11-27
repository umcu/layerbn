"""Write the design workbook that `layerbn init` hands to a new user.

The workbook has an instructions sheet and the three sheets read by
`layerbn.design`. Layer names, yes/no fields and variable types are dropdown
lists, so the most common mistakes (a layer name spelt differently in two
places, `Yes` where `yes` was expected) cannot be typed in.
"""
from __future__ import annotations

from pathlib import Path

VARIABLE_HEADERS = ["variable", "label", "layer", "type", "bins", "cutpoints",
                    "times", "target", "note"]
LAYER_HEADERS = ["layer", "label", "repeated", "arcs_within", "colour", "note"]
TIME_HEADERS = ["time", "label"]

# variable, label, layer, type, bins, cutpoints, times, target, note
DEMO_VARIABLES = [
    ["AGE", "Age (years)", "Background", "", "", "", "", "", ""],
    ["SEX", "Sex", "Background", "categorical", "", "", "", "", ""],
    ["EXPOSURE_A", "Exposure A (score)", "Exposures", "", "", "", "", "", ""],
    ["EXPOSURE_B", "Exposure B", "Exposures", "categorical", "", "", "", "", ""],
    ["MEASURE_1", "Measure 1", "Baseline measures", "", "", "", "", "", ""],
    ["MEASURE_2", "Measure 2", "Baseline measures", "", "", "", "", "", ""],
    ["MEASURE_3", "Measure 3", "Baseline measures", "", "", "", "", "", ""],
    ["OUTCOME", "Outcome at follow-up", "Outcome", "categorical", "", "", "",
     "yes", "The variable of main interest: marked as target."],
]
DEMO_LAYERS = [
    ["Background", "", "no", "", "", "First layer: nothing in the study causes these."],
    ["Exposures", "", "no", "", "", ""],
    ["Baseline measures", "", "no", "", "", ""],
    ["Outcome", "", "no", "no", "", "Last layer. arcs_within = no: no arcs inside it."],
]
# The example has no repeated measures, so the time points sheet stays empty.
DEMO_TIMEPOINTS: list[list[str]] = []

INSTRUCTIONS = [
    ("How to fill in this workbook", None),
    ("", None),
    ("This workbook describes your study to layerbn. It has three sheets that "
     "you edit: variables, layers and timepoints.", None),
    ("", None),
    ("1. Layers (sheet 'layers')", "h"),
    ("A layer is a group of variables that can influence each other but that "
     "come at the same stage of the causal order, for example background "
     "characteristics, exposures, measurements, outcomes.", None),
    ("The ORDER OF THE ROWS is the causal order. An arc in the network may "
     "only run from a layer to itself or to a layer further down the list. "
     "Put what can cause something above what it can cause. A variable that "
     "is measured later in time belongs below one measured earlier.", None),
    ("Columns: layer (the name; a short name works best), label (optional "
     "display name), repeated (yes if the layer is measured at every time "
     "point), arcs_within (no if variables in the same layer should not be "
     "connected; empty uses the setting in settings.yml), colour (optional; "
     "a name such as 'steelblue' or a hex code).", None),
    ("", None),
    ("2. Variables (sheet 'variables')", "h"),
    ("One row per variable. Choose the layer from the dropdown list.", None),
    ("variable: the column name in your data file, exactly as written there. "
     "For a repeated layer give the name without the time point (SCORE, "
     "not SCORE_T0). The data columns are then SCORE_T0, SCORE_T1 and so "
     "on; the pattern is set in settings.yml.", None),
    ("label: the name shown in figures and tables. Empty uses the column name.", None),
    ("type: leave empty to let layerbn decide. A number with more than 10 "
     "different values is cut into bins; anything else is used as it is. "
     "Write 'categorical' to use a numeric variable without binning (for "
     "example a group coded 1, 2, 3). Write 'continuous' to bin a "
     "numeric variable that has few different values.", None),
    ("bins: number of bins for this variable, if it should differ from the "
     "default in settings.yml.", None),
    ("cutpoints: your own thresholds, separated by semicolons, for example "
     "'24; 27' gives three groups: below 24, 24 up to 27, and 27 or higher. "
     "Use this for established cut-offs. Use a full stop or a comma as the "
     "decimal mark.", None),
    ("times: for a repeated layer, the time points at which the variable is "
     "measured, separated by semicolons. Empty means all time points.", None),
    ("target: yes for the variables you are mainly interested in, for "
     "example the outcomes. They are the default choice in the analyses that "
     "ask for a target. If none is marked, the last layer is used.", None),
    ("", None),
    ("3. Time points (sheet 'timepoints')", "h"),
    ("Only needed if the same variables were measured more than once and a "
     "layer is marked as repeated; otherwise leave this sheet empty. One row "
     "per measurement occasion, in time order. 'time' is the text in the "
     "column names (T0, T1, ...), 'label' is what readers see (First visit, "
     "Second visit, ...).", None),
    ("The layers that are marked as repeated must follow each other. They "
     "are expanded into one block per time point, in time order, at the "
     "position of the first repeated layer.", None),
    ("", None),
    ("Columns named 'note' or 'comment' are ignored. Delete the example rows "
     "before you add your own, or start from 'layerbn init --blank'.", None),
]


def write_design_workbook(path: str | Path, *, demo: bool = True) -> Path:
    """Write the workbook. With `demo=False` the three sheets are empty."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    path = Path(path)
    workbook = Workbook()

    guide = workbook.active
    guide.title = "instructions"
    guide.column_dimensions["A"].width = 110
    for row, (text, style) in enumerate(INSTRUCTIONS, start=1):
        cell = guide.cell(row=row, column=1, value=text)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if row == 1:
            cell.font = Font(bold=True, size=14)
        elif style == "h":
            cell.font = Font(bold=True, size=12)

    header_fill = PatternFill("solid", fgColor="E8EEF4")

    def sheet(name: str, headers: list[str], rows: list[list[str]],
              widths: list[int]):
        ws = workbook.create_sheet(name)
        ws.append(headers)
        for row in rows:
            ws.append(row)
        for i, width in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = width
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
        ws.freeze_panes = "A2"
        return ws

    variables = sheet("variables", VARIABLE_HEADERS,
                      DEMO_VARIABLES if demo else [],
                      [22, 28, 20, 14, 8, 16, 14, 8, 50])
    layers = sheet("layers", LAYER_HEADERS, DEMO_LAYERS if demo else [],
                   [22, 24, 10, 12, 12, 50])
    sheet("timepoints", TIME_HEADERS, DEMO_TIMEPOINTS if demo else [], [12, 20])

    last = 300

    def dropdown(ws, column: str, formula: str) -> None:
        validation = DataValidation(type="list", formula1=formula,
                                    allow_blank=True, showErrorMessage=True)
        validation.error = "Choose a value from the list."
        ws.add_data_validation(validation)
        validation.add(f"{column}2:{column}{last}")

    dropdown(variables, "C", f"=layers!$A$2:$A${last}")
    dropdown(variables, "D", '"categorical,continuous"')
    dropdown(variables, "H", '"yes,no"')
    dropdown(layers, "C", '"yes,no"')
    dropdown(layers, "D", '"yes,no"')

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path
