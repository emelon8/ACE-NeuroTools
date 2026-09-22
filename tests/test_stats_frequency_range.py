"""Regression coverage for effective frequency-range propagation (#110)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from aceneurotools.config.lab_config import ConditionSpec, LabConfig
from aceneurotools.config.stats_config import StatsConfig, StudyMetadata


@pytest.fixture
def stats_pipeline_module(monkeypatch):
    """Load the pipeline without importing its CaImAn-dependent data loader."""
    loader = ModuleType("aceneurotools.stats.loader")
    loader.load_calcium_signal = lambda *args, **kwargs: None
    loader.load_for_stats = lambda *args, **kwargs: None
    loader.load_for_stats_two_channels = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, loader.__name__, loader)

    path = Path(__file__).resolve().parents[1] / "src/aceneurotools/pipelines/stats.py"
    spec = importlib.util.spec_from_file_location("_stats_frequency_range_regression", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("explicit_range", "use_lab_config", "expected_range"),
    [
        (None, False, [0.5, 4.0]),
        (None, True, [4.0, 8.0]),
        ([8.0, 12.0], True, [8.0, 12.0]),
    ],
    ids=["stats-config-default", "lab-config-override", "explicit-override"],
)
def test_effective_frequency_range_reaches_all_engines_and_provenance(
    stats_pipeline_module,
    monkeypatch,
    tmp_path,
    explicit_range,
    use_lab_config,
    expected_range,
):
    module = stats_pipeline_module
    original_config = StatsConfig(lowcut=0.5, highcut=4.0)
    metadata = StudyMetadata(
        drug_groups={"drug": [7]},
        selections={7: [[0.0, 1.0], [1.0, 2.0]]},
    )
    lab_config = (
        LabConfig(
            primary_channel="primary",
            secondary_channel="secondary",
            freq_range=[4.0, 8.0],
            conditions={"drug": ConditionSpec(subjects=[7], is_drug=True)},
            time_windows={7: [[0.0, 1.0], [1.0, 2.0]]},
        )
        if use_lab_config
        else None
    )

    dispatched = []

    def capture_dispatch(self, **kwargs):
        dispatched.append((kwargs["config"], kwargs["freq_range"]))

    monkeypatch.setattr(module.StatsPipeline, "_run_coherence_ephys_calcium", capture_dispatch)
    monkeypatch.setattr(module.StatsPipeline, "_run_coherence_ephys_ephys", capture_dispatch)
    monkeypatch.setattr(module.StatsPipeline, "_run_scatter_correlation", capture_dispatch)

    output_dir = tmp_path / "results"
    module.StatsPipeline().run(
        project_path=tmp_path,
        output_dir=output_dir,
        analyses=list(module.VALID_ANALYSES),
        line_nums=[7],
        freq_range=explicit_range,
        stats_config=original_config,
        study_metadata=metadata,
        lab_config=lab_config,
        headless=True,
    )

    assert len(dispatched) == 3
    for effective_config, dispatched_range in dispatched:
        assert [effective_config.lowcut, effective_config.highcut] == expected_range
        assert dispatched_range == expected_range
        assert effective_config.headless is True

    run_params = json.loads((output_dir / "run_log.json").read_text())["params"]
    assert run_params["freq_range_hz"] == expected_range
    assert [run_params["stats_config"]["lowcut"], run_params["stats_config"]["highcut"]] == expected_range

    # Resolving one run must not rewrite a reusable caller-owned config object.
    assert [original_config.lowcut, original_config.highcut] == [0.5, 4.0]
    assert original_config.headless is False
