"""Project configuration loading.

A project's `config.yml` is the single source of truth for paths and
per-run knobs. Every project supplies its own file; `PreprocessConfig`
just holds the parsed values and resolves relative paths against
`project_root`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass
class PreprocessConfig:
    """Parsed contents of a project `config.yml`.

    Extra keys the caller doesn't know about are preserved in `extra` so
    projects can add cohort-specific settings without needing a code change.
    """

    project_root: Path
    raw_dir: Path
    output_dir: Path
    codebook_path: Path | None = None
    risk_region: str = "Low"
    seed: int = 1234
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.project_root = self._resolve(self.project_root)
        self.raw_dir = self._resolve(self.raw_dir)
        self.output_dir = self._resolve(self.output_dir)
        if self.codebook_path is not None:
            self.codebook_path = self._resolve(self.codebook_path)

    def _resolve(self, p: str | Path) -> Path:
        path = Path(p).expanduser()
        if not path.is_absolute():
            path = (self.project_root / path).resolve()
        return path


_REQUIRED_KEYS = ("project_root", "raw_dir", "output_dir")


def load_project_config(
    path: str | Path | None = None,
    *,
    search_locations: list[Path] | None = None,
) -> PreprocessConfig:
    """Load a project `config.yml` and return a `PreprocessConfig`.

    If `path` is given it is used directly. Otherwise the loader looks for
    `config.yml` in `search_locations` (defaults: cwd, then each parent).
    """
    if path is None:
        candidates = search_locations or _default_search_locations()
        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            raise FileNotFoundError(
                "config.yml not found. Pass an explicit path or run from a "
                "directory containing (or nested under) one."
            )
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a mapping at the top level")

    missing = [k for k in _REQUIRED_KEYS if k not in raw]
    if missing:
        raise KeyError(f"{path} is missing required keys: {missing}")

    known = {"project_root", "raw_dir", "output_dir", "codebook_path",
             "risk_region", "seed"}
    extra = {k: v for k, v in raw.items() if k not in known}
    return PreprocessConfig(
        project_root=Path(raw["project_root"]).expanduser(),
        raw_dir=Path(raw["raw_dir"]).expanduser(),
        output_dir=Path(raw["output_dir"]).expanduser(),
        codebook_path=Path(raw["codebook_path"]).expanduser() if raw.get("codebook_path") else None,
        risk_region=raw.get("risk_region", "Low"),
        seed=int(raw.get("seed", 1234)),
        extra=extra,
    )


def _default_search_locations() -> list[Path]:
    """Look for config.yml next to cwd, then walking up."""
    here = Path.cwd().resolve()
    return [here / "config.yml", *[p / "config.yml" for p in here.parents]]


def apply_overrides(cfg: PreprocessConfig, overrides: Mapping[str, Any]) -> PreprocessConfig:
    """Return a copy of `cfg` with selected fields replaced."""
    from dataclasses import replace
    kwargs: dict[str, Any] = {}
    for key in ("raw_dir", "output_dir", "codebook_path"):
        if key in overrides and overrides[key] is not None:
            kwargs[key] = Path(overrides[key]).expanduser()
    for key in ("risk_region", "seed"):
        if key in overrides:
            kwargs[key] = overrides[key]
    return replace(cfg, **kwargs)
