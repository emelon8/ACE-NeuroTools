"""Configuration failures are actionable and never change subject identity."""

from __future__ import annotations

import copy
import json

import pytest

from aceneurotools.config.config_utils import load_analysis_params, parse_analysis_params
from aceneurotools.config.lab_config import LabConfig
from aceneurotools.config.stats_config import StatsConfig
from aceneurotools.shared.exceptions import ConfigurationError


@pytest.fixture
def lab_data():
    return {
        "primary_channel": "EEG",
        "freq_range": [0.5, 4.0],
        "conditions": {"control": {"subjects": [1], "is_drug": False}},
        "time_windows": {"1": [[0, 1], [2, 3]]},
    }


def load(tmp_path, data):
    path = tmp_path / "lab_config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return LabConfig.from_json(path)


@pytest.mark.parametrize("data", [None, [], "config", 3, True])
def test_nonobject_json_has_configuration_error(tmp_path, data):
    with pytest.raises(ConfigurationError, match="object"):
        load(tmp_path, data)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True, False])
def test_frequency_bounds_must_be_finite_numbers(tmp_path, lab_data, bad):
    lab_data["freq_range"][0] = bad
    with pytest.raises(ConfigurationError, match="freq_range"):
        load(tmp_path, lab_data)


@pytest.mark.parametrize("bad", [True, False, 1.9, "1.9", float("inf"), None])
def test_subject_ids_cannot_be_silently_coerced(tmp_path, lab_data, bad):
    lab_data["conditions"]["control"]["subjects"] = [bad]
    with pytest.raises(ConfigurationError, match="subjects"):
        load(tmp_path, lab_data)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True])
def test_time_windows_require_finite_numeric_values(tmp_path, lab_data, bad):
    lab_data["time_windows"]["1"][0][1] = bad
    with pytest.raises(ConfigurationError, match="time_windows"):
        load(tmp_path, lab_data)


def test_equivalent_time_window_keys_cannot_overwrite_one_another(tmp_path, lab_data):
    lab_data["time_windows"]["01"] = [[10, 11], [12, 13]]
    with pytest.raises(ConfigurationError, match="more than once"):
        load(tmp_path, lab_data)


@pytest.mark.parametrize("bad", [[], {}, None, 3])
def test_bad_run_mode_is_a_configuration_error(tmp_path, lab_data, bad):
    lab_data["run"] = {"mode": bad}
    with pytest.raises(ConfigurationError, match="run.mode"):
        load(tmp_path, lab_data)


@pytest.mark.parametrize("bad", [True, 1.5, None])
def test_explicit_run_line_numbers_are_strict_integers(tmp_path, lab_data, bad):
    lab_data["run"] = {"line_nums": [bad]}
    with pytest.raises(ConfigurationError, match="run.line_nums"):
        load(tmp_path, lab_data)


def test_multiple_errors_are_collected_in_one_message(tmp_path, lab_data):
    lab_data["primary_channel"] = ""
    lab_data["freq_range"] = [4, 0.5]
    lab_data["conditions"]["second"] = {"subjects": [1, 2], "is_drug": "yes"}
    with pytest.raises(ConfigurationError) as error:
        load(tmp_path, lab_data)
    for field in ("primary_channel", "freq_range", "is_drug", "appears in both", "Subject 2"):
        assert field in str(error.value)


def test_lab_roundtrip_and_study_conversion_are_independent(tmp_path, lab_data):
    lab_data["_instructions"] = "ignored documentation"
    lab_data["conditions"]["_notes"] = "ignored documentation"
    lab_data["conditions"]["control"]["subjects"] = ["1"]
    lab_data["paths"] = {"project_path": " /lab/project ", "data_path": " "}
    lab_data["run"] = {"mode": "compute", "headless": True, "history": True}
    config = load(tmp_path, lab_data)
    target = tmp_path / "roundtrip.json"
    config.to_json(target)
    assert LabConfig.from_json(target) == config
    assert config.paths.project_path == "/lab/project"
    assert config.paths.data_path is None
    study = config.to_study_metadata()
    assert study.has_drug_event(1) is False
    study.selections[1][0][0] = 99
    study.drug_groups["control"].append(2)
    assert config.time_windows[1][0][0] == 0
    assert config.all_line_nums() == [1]


def test_stats_config_defaults_do_not_share_mutable_lists(tmp_path):
    config = StatsConfig()
    config.spectrogram_freq_lims[0] = 2
    config.plot_formats.append("png")
    assert StatsConfig().spectrogram_freq_lims == [0, 20]
    assert StatsConfig().plot_formats == ["svg", "tiff"]
    path = tmp_path / "stats.json"
    config.to_json(path)
    assert StatsConfig.from_json(path) == config


@pytest.mark.parametrize(
    "canonical, legacy", [("filter_miniscope_data", "filter_data"), ("compute_miniscope_spectrogram", "spectrogram")]
)
def test_explicit_false_overrides_legacy_true_and_does_not_mutate_input(canonical, legacy):
    source = {canonical: False, legacy: True, "unknown_lab_column": "keep"}
    before = copy.deepcopy(source)
    assert parse_analysis_params(source) == {canonical: False}
    assert source == before


def test_crop_compatibility_explicit_coordinates_win():
    source = {"crop": [0, 1, 10, 11], "crop_coords": [2, 3, 8, 9], "n_processes": None}
    assert parse_analysis_params(source) == {"crop": True, "crop_coords": [2, 3, 8, 9]}


def test_load_analysis_params_never_falls_back_to_another_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "analysis_parameters.csv").write_text("line number,crop\n1,True\n")
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(ValueError, match="project_path is required"):
        load_analysis_params(1)
    with pytest.raises(FileNotFoundError, match="other"):
        load_analysis_params(1, other)
