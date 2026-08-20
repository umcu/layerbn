"""Where this machine keeps its files.

`spec.yml` says what the analysis is; `config.yml` says where the data
sits on the machine running it. Keeping the two apart is what makes the
spec publishable alongside a manuscript — it records the analysis and
nothing about the filesystem it ran on.

A minimal `config.yml`:

    project_root: /home/you/my-study

and everything else is derived from it. To be explicit:

    project_root: /home/you/my-study
    data_dir:     data          # where the analysis-ready table lives
    output_dir:   outputs       # where results are written
    seed:         1234          # for anything outside the spec's own seed

Relative paths resolve against `project_root`; absolute paths are left
alone. Keys this package does not recognise are kept in `extra`, so a
project can carry its own settings in the same file without needing a
change here.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

# Recognised at the top level of config.yml. Anything else lands in `extra`.
_KNOWN_KEYS = frozenset(
    {"project_root", "data_dir", "raw_dir", "output_dir", "codebook_path", "seed"}
)


@dataclass
class ProjectConfig:
    """Parsed contents of a project `config.yml`.

    Attributes
    ----------
    project_root : Path
        The directory every relative path below is resolved against.
    data_dir : Path
        Where the analysis-ready table lives. The spec's `data.path` is
        resolved against this. Defaults to `project_root`.
    output_dir : Path
        Where results are written. Defaults to `project_root/outputs`.
    codebook_path : Path or None
        Optional variable documentation, for the project's own use. This
        package does not read it.
    seed : int
        A seed for project code outside the analysis. The analysis has its
        own seed in `spec.yml`, and that is the one that governs results.
    extra : dict
        Every other key in the file, preserved verbatim.
    """

    project_root: Path
    data_dir: Path | None = None
    output_dir: Path | None = None
    codebook_path: Path | None = None
    seed: int = 1234
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root).expanduser().resolve()
        self.data_dir = self._resolve(self.data_dir if self.data_dir is not None else ".")
        self.output_dir = self._resolve(
            self.output_dir if self.output_dir is not None else "outputs"
        )
        if self.codebook_path is not None:
            self.codebook_path = self._resolve(self.codebook_path)

    def _resolve(self, p: str | Path) -> Path:
        path = Path(p).expanduser()
        if not path.is_absolute():
            path = (self.project_root / path).resolve()
        return path

    def __str__(self) -> str:
        return (f"project_root  {self.project_root}\n"
                f"data_dir      {self.data_dir}\n"
                f"output_dir    {self.output_dir}")


# `PreprocessConfig` was the name up to v1.2.1, when this module also
# carried cohort preprocessing settings. Kept so existing project code
# keeps importing successfully.
PreprocessConfig = ProjectConfig


def load_project_config(
    path: str | Path | None = None,
    *,
    search_locations: list[Path] | None = None,
) -> ProjectConfig:
    """Load a project `config.yml`.

    If `path` is given it is used directly. Otherwise the loader looks for
    `config.yml` in the working directory, then in each parent.

    Only `project_root` is required. A `project_root` that is itself
    relative resolves against the directory holding `config.yml`, so a
    file containing `project_root: .` means "the folder I am in".
    """
    if path is None:
        candidates = search_locations or _default_search_locations()
        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            raise FileNotFoundError(
                "config.yml not found. Pass an explicit path, or run from a "
                "directory containing (or nested under) one."
            )
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a mapping at the top level")

    if "project_root" not in raw:
        raise KeyError(
            f"{path} is missing the required key 'project_root'. "
            "Use `project_root: .` for the directory holding this file."
        )

    root = Path(str(raw["project_root"])).expanduser()
    if not root.is_absolute():
        # Relative to the config file, not to the working directory: the
        # same file then means the same thing whichever folder you run from.
        root = (path.resolve().parent / root).resolve()

    # `raw_dir` was the v1 name for what is now `data_dir`.
    data_dir = raw.get("data_dir", raw.get("raw_dir"))

    return ProjectConfig(
        project_root=root,
        data_dir=Path(str(data_dir)).expanduser() if data_dir is not None else None,
        output_dir=(Path(str(raw["output_dir"])).expanduser()
                    if raw.get("output_dir") is not None else None),
        codebook_path=(Path(str(raw["codebook_path"])).expanduser()
                       if raw.get("codebook_path") else None),
        seed=int(raw.get("seed", 1234)),
        extra={k: v for k, v in raw.items() if k not in _KNOWN_KEYS},
    )


def _default_search_locations() -> list[Path]:
    """`config.yml` in the working directory, then in each parent."""
    here = Path.cwd().resolve()
    return [here / "config.yml", *[p / "config.yml" for p in here.parents]]


def apply_overrides(cfg: ProjectConfig, overrides: Mapping[str, Any]) -> ProjectConfig:
    """Return a copy of `cfg` with selected fields replaced.

    Paths are re-resolved against `project_root`, so a relative override
    means the same thing it would have meant in the file.
    """
    kwargs: dict[str, Any] = {}
    for key in ("data_dir", "output_dir", "codebook_path"):
        if overrides.get(key) is not None:
            kwargs[key] = Path(overrides[key]).expanduser()
    if "seed" in overrides:
        kwargs["seed"] = int(overrides["seed"])
    return replace(cfg, **kwargs)
