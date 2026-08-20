"""config.yml: where the files are, kept apart from what the analysis is."""
from __future__ import annotations

import pytest

from layerbn.config import ProjectConfig, load_project_config


def write(tmp_path, text, name="config.yml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_only_project_root_is_required(tmp_path):
    config = load_project_config(write(tmp_path, "project_root: .\n"))
    assert config.project_root == tmp_path.resolve()
    assert config.data_dir == tmp_path.resolve()
    assert config.output_dir == (tmp_path / "outputs").resolve()


def test_relative_project_root_resolves_against_the_config_file(tmp_path):
    """The same file must mean the same thing from any working directory."""
    nested = tmp_path / "study"
    nested.mkdir()
    path = write(nested, "project_root: .\ndata_dir: data\n")

    config = load_project_config(path)
    assert config.project_root == nested.resolve()
    assert config.data_dir == (nested / "data").resolve()


def test_absolute_paths_are_left_alone(tmp_path):
    elsewhere = tmp_path / "mounted"
    elsewhere.mkdir()
    config = load_project_config(
        write(tmp_path, f"project_root: .\ndata_dir: {elsewhere}\n")
    )
    assert config.data_dir == elsewhere.resolve()


def test_raw_dir_is_accepted_as_the_old_name_for_data_dir(tmp_path):
    config = load_project_config(write(tmp_path, "project_root: .\nraw_dir: incoming\n"))
    assert config.data_dir == (tmp_path / "incoming").resolve()


def test_missing_project_root_names_the_key(tmp_path):
    with pytest.raises(KeyError, match="project_root"):
        load_project_config(write(tmp_path, "data_dir: data\n"))


def test_unknown_keys_are_preserved(tmp_path):
    """A project must be able to keep its own settings in the same file."""
    config = load_project_config(
        write(tmp_path, "project_root: .\ncohort_name: HBC\nfollow_up_years: 4\n")
    )
    assert config.extra == {"cohort_name": "HBC", "follow_up_years": 4}


def test_a_missing_file_says_so(tmp_path):
    with pytest.raises(FileNotFoundError, match="config.yml"):
        load_project_config(search_locations=[tmp_path / "absent.yml"])


def test_preprocess_config_alias_still_imports():
    """v1 code did `from ... import PreprocessConfig`; keep it working."""
    from layerbn.config import PreprocessConfig

    assert PreprocessConfig is ProjectConfig
