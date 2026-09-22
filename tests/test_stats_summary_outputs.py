"""Regression coverage for all-drugs summary handling (#111)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

import aceneurotools.stats.scatter_analysis as scatter_module
from aceneurotools.config.stats_config import StatsConfig, StudyMetadata


@pytest.fixture
def stats_pipeline_module(monkeypatch):
    """Load the pipeline with deterministic in-memory stats data."""
    signal = np.ones(120)
    loader = ModuleType("aceneurotools.stats.loader")
    loader.load_for_stats = lambda **kwargs: (
        SimpleNamespace(signal=signal),
        None,
        30.0,
    )
    loader.load_for_stats_two_channels = lambda **kwargs: None
    loader.load_calcium_signal = lambda *args, **kwargs: signal
    monkeypatch.setitem(sys.modules, loader.__name__, loader)

    path = Path(__file__).resolve().parents[1] / "src/aceneurotools/pipelines/stats.py"
    spec = importlib.util.spec_from_file_location("_stats_summary_regression", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


class _SuccessfulScatter:
    """Populate the real collectors without running per-subject plotting."""

    def __init__(self, config):
        self.config = config

    def run_subject(self, *, line_num, collector, **kwargs):
        control = {
            "r": 0.1 + line_num / 100,
            "ci_lower": 0.0,
            "ci_upper": 0.5,
            "n_effective": 20,
        }
        treatment = dict(control, r=control["r"] + 0.1)
        collector.add_subject(line_num, control, treatment)
        return True, control, treatment


def _run_two_condition_pipeline(module, tmp_path, monkeypatch):
    metadata = StudyMetadata(
        drug_groups={"drug-a": [1, 2], "drug-b": [3, 4]},
        selections={line_num: [[0.0, 0.02], [0.02, 0.04]] for line_num in range(1, 5)},
    )
    monkeypatch.setattr(module, "ScatterAnalysis", _SuccessfulScatter)
    monkeypatch.setattr(
        scatter_module,
        "create_population_violin_plot",
        lambda **kwargs: (None, {}),
    )
    output_dir = tmp_path / "results"
    module.StatsPipeline().run(
        project_path=tmp_path,
        output_dir=output_dir,
        calcium_signal_dir=tmp_path,
        analyses=["scatter_correlation"],
        line_nums=[1, 2, 3, 4],
        study_metadata=metadata,
        stats_config=StatsConfig(
            headless=True,
            bootstrap_iterations=10,
            min_subjects_for_stats=2,
            plot_formats=["png"],
        ),
        headless=True,
    )
    return output_dir


def test_multi_condition_pipeline_writes_labeled_all_drugs_summary(
    stats_pipeline_module,
    monkeypatch,
    tmp_path,
):
    received_keys = []
    real_summary = scatter_module.create_all_drugs_summary_plot

    def capture_summary(*, all_collectors, **kwargs):
        received_keys.extend(all_collectors.keys())
        return real_summary(all_collectors=all_collectors, **kwargs)

    monkeypatch.setattr(
        scatter_module,
        "create_all_drugs_summary_plot",
        capture_summary,
    )

    output_dir = _run_two_condition_pipeline(
        stats_pipeline_module,
        tmp_path,
        monkeypatch,
    )

    assert received_keys == ["drug-a", "drug-b"]
    assert (
        output_dir / "scatter_correlation/population_all_drugs_summary_CBvsPCEEG.png"
    ).is_file()
    assert (
        output_dir / "scatter_correlation/population_all_drugs_summary_CBvsPCEEG.pdf"
    ).is_file()


def test_all_drugs_summary_failure_is_recorded_separately_from_subjects(
    stats_pipeline_module,
    monkeypatch,
    tmp_path,
):
    def fail_summary(**kwargs):
        raise RuntimeError("summary renderer failed")

    monkeypatch.setattr(
        scatter_module,
        "create_all_drugs_summary_plot",
        fail_summary,
    )

    output_dir = _run_two_condition_pipeline(
        stats_pipeline_module,
        tmp_path,
        monkeypatch,
    )
    log = json.loads((output_dir / "run_log.json").read_text())

    assert len(log["completed"]) == 4
    assert log["skipped"] == []
    assert log["output_failures"] == [
        {
            "analysis": "scatter_correlation",
            "output": "all_drugs_summary_plot",
            "reason": "summary renderer failed",
        }
    ]
