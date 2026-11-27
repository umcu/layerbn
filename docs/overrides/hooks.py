"""MkDocs hook: build the live example shown in the documentation.

Before the site is built, the example study that `layerbn init` creates is run
once, and its report and interactive explorer are copied to `docs/generated/`
(not in version control). The documentation then always shows what the
current code produces, and the repository does not carry a 3 MB report.

The run is skipped when the files exist. Set LAYERBN_DOCS_REFRESH=1 to run it
again, for example after a change to the figures.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import warnings
from pathlib import Path

GENERATED = Path(__file__).resolve().parent.parent / "generated"
OUTPUTS = {
    "example-report.html": "report.html",
    "example-explorer.html": "networks/all_variables_explorer.html",
}


def on_pre_build(config, **kwargs) -> None:  # noqa: ARG001 - MkDocs hook signature
    wanted = [GENERATED / name for name in OUTPUTS]
    if all(p.exists() for p in wanted) and not os.environ.get("LAYERBN_DOCS_REFRESH"):
        return

    from layerbn.__main__ import main

    GENERATED.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp, warnings.catch_warnings():
        warnings.simplefilter("ignore")
        study = Path(tmp) / "example"
        if main(["init", str(study)]) != 0 or main(["run", str(study)]) != 0:
            raise RuntimeError("the example study could not be run for the documentation")
        for name, source in OUTPUTS.items():
            shutil.copyfile(study / "results" / source, GENERATED / name)
