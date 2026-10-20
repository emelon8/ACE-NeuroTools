"""The shared API has generic names without changing legacy analysis behavior."""

import importlib
import inspect
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, asdict
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from aceneurotools.calcium_imaging import PostprocessConfig, PostprocessingResult, Projections
from aceneurotools.calcium_imaging.filtered_calcium_imaging_data import FilterCalciumImagingData
from aceneurotools.shared.calcium_imaging_names import LEGACY_OPTIONS
from aceneurotools.shared.cli_utils import build_run_params, run_allowed_keys, validate_run_params
from aceneurotools.shared.config_utils import parse_analysis_params
from aceneurotools.shared.pipeline_defaults import pipeline_defaults


@pytest.mark.parametrize("old,new,symbol,canonical", [
    ("miniscope.miniscope_data_manager", "calcium_imaging.calcium_imaging_data_manager", "MiniscopeDataManager", "CalciumImagingDataManager"),
    ("miniscope.miniscope_preprocessor", "calcium_imaging.calcium_imaging_preprocessor", "MiniscopePreprocessor", "CalciumImagingPreprocessor"),
    ("miniscope.miniscope_processor", "calcium_imaging.calcium_imaging_processor", "MiniscopeProcessor", "CalciumImagingProcessor"),
    ("miniscope.miniscope_postprocessor", "calcium_imaging.calcium_imaging_postprocessor", "MiniscopePostprocessor", "CalciumImagingPostprocessor"),
    ("miniscope.filtered_miniscope_data", "calcium_imaging.filtered_calcium_imaging_data", "FilterMiniscopeData", "FilterCalciumImagingData"),
    ("pipelines.miniscope", "pipelines.calcium_imaging", "MiniscopePipeline", "CalciumImagingPipeline"),
])
def test_old_imports_share_the_canonical_class_and_module(old, new, symbol, canonical):
    previous = importlib.import_module(f"aceneurotools.{old}")
    current = importlib.import_module(f"aceneurotools.{new}")
    if old != "pipelines.miniscope":
        assert previous is current
    assert getattr(previous, symbol) is getattr(current, canonical)
    assert getattr(current, canonical).__name__ == canonical


def test_lightweight_import_does_not_load_caiman():
    result = subprocess.run(
        [sys.executable, "-c", "import sys; import aceneurotools.calcium_imaging; assert 'caiman' not in sys.modules"],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
    )
    assert result.returncode == 0, result.stderr


def test_legacy_config_keywords_and_attributes_share_canonical_values():
    config = PostprocessConfig(compute_miniscope_phase=False, filter_miniscope_data=False)
    assert not config.compute_calcium_imaging_phase
    assert not config.filter_calcium_imaging_data
    config.compute_miniscope_phase = True
    assert config.compute_calcium_imaging_phase
    config.filter_calcium_imaging_data = True
    assert config.filter_miniscope_data
    assert "compute_miniscope_phase" not in asdict(config)
    with pytest.raises(TypeError, match="Use only one"):
        PostprocessConfig(compute_miniscope_phase=False, compute_calcium_imaging_phase=True)


def test_result_phase_alias_preserves_frozen_result_contract():
    phases = np.arange(10)
    result = PostprocessingResult(None, None, None, None, None, None, miniscope_phases=phases, filter_object=None)
    assert result.calcium_imaging_phases is result.miniscope_phases is phases
    assert "calcium_imaging_phases" in asdict(result)
    with pytest.raises(FrozenInstanceError):
        result.miniscope_phases = None


def test_filter_alias_produces_the_same_signal():
    t = np.arange(600) / 30
    signal = np.sin(2 * np.pi * .5 * t) + .5 * np.sin(2 * np.pi * 5 * t)
    zero = np.zeros((2, 2))
    projections = Projections(zero, zero, zero, zero, zero, zero, signal)
    canonical = FilterCalciumImagingData(projections, 30)
    historical = FilterCalciumImagingData(projections, 30)
    canonical.filter_calcium_imaging_data()
    historical.filter_miniscope_data()
    np.testing.assert_array_equal(canonical.filtered_data, historical.filtered_data)
    assert not np.allclose(canonical.filtered_data, signal)


@pytest.mark.parametrize("kind", ["calcium_imaging", "multimodal"])
def test_legacy_csv_options_reach_canonical_cli_signature(kind, tmp_path):
    from aceneurotools.pipelines.calcium_imaging import CalciumImagingPipeline
    from aceneurotools.pipelines.multimodal import MultimodalPipeline

    method = CalciumImagingPipeline.run if kind == "calcium_imaging" else MultimodalPipeline.run
    options = build_run_params(
        defaults=pipeline_defaults(kind), allowed_keys=run_allowed_keys(method),
        line_num=1, project_path=str(tmp_path), data_path=None, headless=True,
        csv_loader=lambda *args, **kwargs: parse_analysis_params({
            "compute_miniscope_phase": False, "filter_data": False, "spectrogram": False,
        }),
    )
    bound = inspect.signature(method).bind(None, **options)
    assert bound.arguments["compute_calcium_imaging_phase"] is False
    assert bound.arguments["filter_calcium_imaging_data"] is False
    assert bound.arguments["compute_calcium_imaging_spectrogram"] is False
    assert not (set(LEGACY_OPTIONS) & options.keys())
    validate_run_params(pipeline_name=kind, run_params=options)


def test_new_csv_spelling_overrides_old_spelling_in_cli_and_gui(tmp_path):
    from aceneurotools.gui.run_specs import effective_parameters
    from aceneurotools.pipelines.calcium_imaging import CalciumImagingPipeline

    raw = {"compute_miniscope_phase": True, "compute_calcium_imaging_phase": False}
    options = build_run_params(
        defaults=pipeline_defaults("calcium_imaging"), allowed_keys=run_allowed_keys(CalciumImagingPipeline.run),
        line_num=1, project_path=str(tmp_path), data_path=None, headless=True,
        csv_loader=lambda *args, **kwargs: parse_analysis_params(raw),
    )
    assert options["compute_calcium_imaging_phase"] is False
    gui, _ = effective_parameters("miniscope", raw)
    assert gui["compute_miniscope_phase"] is False


def test_shared_manager_and_multimodal_attribute_aliases():
    from aceneurotools.calcium_imaging.calcium_imaging_data_manager import CalciumImagingDataManager
    from aceneurotools.miniscope.miniscope_data_manager import MiniscopeDataManager
    from aceneurotools.miniscope.onix_miniscope_data_manager import OnixMiniscopeDataManager
    from aceneurotools.miniscope.ucla_data_manager import UCLADataManager
    from aceneurotools.pipelines import CalciumImagingPipeline, MiniscopePipeline
    from aceneurotools.pipelines.multimodal import MultimodalPipeline

    assert CalciumImagingDataManager is MiniscopeDataManager
    assert CalciumImagingPipeline is MiniscopePipeline
    assert issubclass(UCLADataManager, CalciumImagingDataManager)
    assert issubclass(OnixMiniscopeDataManager, CalciumImagingDataManager)
    pipeline = MultimodalPipeline()
    assert pipeline.calcium_imaging_pipeline is pipeline.miniscope_pipeline
    marker = object()
    pipeline.miniscope_pipeline.miniscope_data_manager = marker
    assert pipeline.calcium_imaging_pipeline.calcium_imaging_data_manager is marker


@pytest.mark.parametrize("legacy", [False, True])
def test_postprocessing_generic_and_legacy_flags_match(legacy):
    from aceneurotools.calcium_imaging.calcium_imaging_postprocessor import CalciumImagingPostprocessor

    t = np.arange(400) / 30
    raw = np.sin(2 * np.pi * .5 * t)
    dm = SimpleNamespace(
        movie=np.broadcast_to(raw[:, None, None], (400, 2, 2)).copy(), fr=30., dview=None,
        CNMFE_obj=None, ca_events_idx=None, PSD_spect=None, t_spect=None,
        freqs_spect=None, p_spect=None, miniscope_phases=None, filter_object=None,
    )
    processor = CalciumImagingPostprocessor(dm)
    flags = {
        "compute_calcium_imaging_phase": True,
        "filter_calcium_imaging_data": True,
        "compute_calcium_imaging_spectrogram": False,
    }
    if legacy:
        inverse = {new: old for old, new in LEGACY_OPTIONS.items()}
        flags = {inverse.get(key, key): value for key, value in flags.items()}
    processor.postprocess_calcium_movie(
        remove_components_with_gui=False, find_calcium_events=False, inline=True, **flags,
    )
    np.testing.assert_allclose(dm.calcium_imaging_phases, processor.compute_calcium_imaging_phase(raw))
    np.testing.assert_allclose(dm.projections.time, dm.filter_object.filtered_data)
    assert processor.result.miniscope_phases is processor.result.calcium_imaging_phases


def test_event_phase_helper_supports_both_names_and_keywords():
    from aceneurotools.multimodal.phase_utils import calcium_imaging_phase_ca_events, miniscope_phase_ca_events

    phases = np.arange(10, dtype=float)
    events = {0: np.array([2, 5, 8])}
    new = calcium_imaging_phase_ca_events(events, calcium_imaging_phases=phases)
    old = miniscope_phase_ca_events(events, miniscope_phases=phases)
    np.testing.assert_array_equal(new[0], phases[[2, 5, 8]])
    np.testing.assert_array_equal(new[0], old[0])


@pytest.mark.parametrize("old,new", LEGACY_OPTIONS.items())
@pytest.mark.parametrize("source", ["parser", "csv", "manager"])
def test_programmatic_parameters_prefer_new_csv_spelling(old, new, source, tmp_path):
    from aceneurotools.pipelines.calcium_imaging import CalciumImagingPipeline
    from aceneurotools.pipelines.multimodal import MultimodalPipeline
    from aceneurotools.shared.config_utils import load_analysis_params
    from aceneurotools.shared.experiment_data_manager import ExperimentDataManager

    previous, canonical = (["old.avi"], ["new.avi"]) if "filenames" in old else (True, False)
    raw = {old: previous, new: canonical}
    if source == "parser":
        params = parse_analysis_params(raw)
    elif source == "csv":
        import csv

        with (tmp_path / "analysis_parameters.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["line number", old, new])
            writer.writeheader()
            writer.writerow({"line number": 1, **raw})
        params = load_analysis_params(1, project_path=tmp_path)
    else:
        manager = object.__new__(ExperimentDataManager)
        manager.analysis_params = raw
        params = manager.get_pipeline_params()

    assert params == {new: canonical}
    # These mappings can be unpacked directly into the documented public API.
    method = MultimodalPipeline.run if "filenames" in old else CalciumImagingPipeline.run
    bound = inspect.signature(method).bind_partial(None, line_num=1, **params)
    assert bound.arguments[new] == canonical
