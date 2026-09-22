"""Phase 3 pipeline hooks: RunRecorder lifecycle, the StatsPipeline
integration (fast, no caiman), run-failure journaling, and the
recorder=None off switch — plus the bug-3 precondition (engine-reported
scatter failures must never be logged as completed)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from aceneurotools.config.stats_config import StudyMetadata
from aceneurotools.evc.hooks import RunRecorder
from aceneurotools.evc.pointers import verify_manifest
from aceneurotools.evc.porcelain import ExperimentVersionControl

AUTHOR = "Test Rig <rig@lab>"


@pytest.fixture()
def exp(tmp_path):
    """An EVC-tracked workspace experiment directory."""
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir()
    ExperimentVersionControl.init(exp_dir, workspace=True)
    return exp_dir


# -- RunRecorder unit tests (stub pipeline) -----------------------------------


def test_on_run_approved_records_pre_revision(exp):
    recorder = RunRecorder(exp, pipeline="stub", line=97, author=AUTHOR)
    pre = recorder.on_run_approved({"gSig": 3}, config_paths=["lab_config.json"])
    evc = ExperimentVersionControl.open(exp)
    revision = evc.show(pre)
    assert revision.message == "run approved: stub line 97"
    assert "parameters/effective_run_params.json" in revision.files
    written = json.loads((exp / "parameters" / "effective_run_params.json").read_text())
    assert written["params"] == {"gSig": 3}
    assert written["config_paths"] == ["lab_config.json"]
    assert written["pipeline"] == "stub"


def test_on_run_completed_links_revisions_and_manifests(exp, tmp_path):
    run_dir = tmp_path / "outputs"
    run_dir.mkdir()
    (run_dir / "result.npz").write_bytes(b"payload")
    run_log = run_dir / "run_log.json"
    run_log.write_text(json.dumps({"completed": [{"line_num": 97}]}, indent=2))

    recorder = RunRecorder(exp, pipeline="stub", line=97, author=AUTHOR)
    pre = recorder.on_run_approved({"gSig": 3})
    post = recorder.on_run_completed(run_dir, run_log=run_log, run_id="run-001")

    log = json.loads(run_log.read_text())
    assert log["evc_pre_revision"] == pre
    assert log["evc_post_revision"] == post
    assert log["completed"] == [{"line_num": 97}]  # original content preserved

    evc = ExperimentVersionControl.open(exp)
    assert [r.oid for r in evc.history()] == [post, pre]
    assert "results/run-001/manifest.json" in evc.show(post).files
    report = verify_manifest(exp / "results" / "run-001")
    assert report.clean and report.verified == ("result.npz",)


def test_identical_reapproval_reuses_head_revision(exp):
    recorder = RunRecorder(exp, pipeline="stub", author=AUTHOR)
    first = recorder.on_run_approved({"gSig": 3})
    again = RunRecorder(exp, pipeline="stub", author=AUTHOR).on_run_approved({"gSig": 3})
    assert again == first
    assert len(ExperimentVersionControl.open(exp).history()) == 1


def test_on_run_failed_journals_without_revision_or_ref_move(exp):
    recorder = RunRecorder(exp, pipeline="stub", line=97, author=AUTHOR)
    recorder.on_run_approved({"gSig": 3})
    evc = ExperimentVersionControl.open(exp)
    head_before = evc.repo.refs.head_oid()
    recorder.on_run_failed(RuntimeError("boom"))
    assert evc.repo.refs.head_oid() == head_before
    assert len(evc.history()) == 1  # failed runs never appear in history
    failures = [e for e in evc.recover() if e.op == "run-failed"]
    assert len(failures) == 1
    assert "RuntimeError: boom" in failures[0].message
    assert "stub line 97" in failures[0].message


# -- StatsPipeline integration (fast, no caiman) ------------------------------


class _StubScatterEngine:
    """Stands in for ScatterAnalysis: writes one artifact, reports success."""

    succeed = True

    def __init__(self, config) -> None:
        self.config = config

    def run_subject(self, **kwargs):
        output_dir = Path(kwargs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "scatter.png").write_bytes(b"png-bytes")
        if not self.succeed:
            return False, None, None
        return True, {"r": 0.5}, {"r": 0.6}


class _FailingScatterEngine(_StubScatterEngine):
    succeed = False


def _run_stats(project, monkeypatch, engine, recorder=None):
    import aceneurotools.pipelines.stats as stats_mod

    channel = SimpleNamespace(signal=np.linspace(0.0, 1.0, 600))
    monkeypatch.setattr(
        stats_mod, "load_for_stats", lambda **kwargs: (channel, None, 10.0)
    )
    monkeypatch.setattr(
        stats_mod, "load_calcium_signal", lambda dm, d, n: np.ones(600)
    )
    monkeypatch.setattr(stats_mod, "ScatterAnalysis", engine)

    meta = StudyMetadata(
        drug_groups={"drugA": [97]},
        selections={97: [[0.0, 0.5], [0.5, 1.0]]},
        no_drug_conditions=set(),
    )
    pipeline = stats_mod.StatsPipeline()
    pipeline.run(
        project_path=project,
        output_dir=project / "stats_results",
        calcium_signal_dir=project / "calcium_signals",
        analyses=["scatter_correlation"],
        line_nums=[97],
        study_metadata=meta,
        headless=True,
        recorder=recorder,
    )
    return json.loads((project / "stats_results" / "run_log.json").read_text())


def test_scatter_engine_failure_logged_as_skip_not_completed(tmp_path, monkeypatch):
    """Bug 3 (2026-09-15 audit): run_subject swallows exceptions and returns
    success=False; the pipeline must not notarise that as completed."""
    project = tmp_path / "project"
    project.mkdir()
    log = _run_stats(project, monkeypatch, _FailingScatterEngine)
    assert log["completed"] == []
    assert [entry["line_num"] for entry in log["skipped"]] == [97]
    assert "scatter analysis failed" in log["skipped"][0]["reason"]


def test_stats_run_with_recorder_yields_two_linked_revisions(tmp_path, monkeypatch):
    """Phase 3 acceptance: one run → pre+post revisions, ids in run_log.json."""
    project = tmp_path / "project"
    project.mkdir()
    ExperimentVersionControl.init(project, workspace=True)
    recorder = RunRecorder(project, pipeline="stats", line=[97], author=AUTHOR)

    log = _run_stats(project, monkeypatch, _StubScatterEngine, recorder=recorder)

    evc = ExperimentVersionControl.open(project)
    history = evc.history()
    assert len(history) == 2
    assert log["evc_pre_revision"] == history[1].oid
    assert log["evc_post_revision"] == history[0].oid
    assert log["completed"] == [{"line_num": 97, "analysis": "scatter_correlation"}]
    run_dirs = list((project / "results").iterdir())
    assert len(run_dirs) == 1 and run_dirs[0].name.startswith("stats-")
    report = verify_manifest(run_dirs[0])
    assert report.clean
    assert any(rel.endswith("scatter.png") for rel in report.verified)
    # the run log is linked metadata, deliberately not a manifested artifact
    assert "run_log.json" not in report.verified


def test_stats_run_failure_reaches_recorder_journal(tmp_path, monkeypatch):
    """A run-level failure journals op=run-failed; no post-run revision."""
    import aceneurotools.pipelines.stats as stats_mod

    project = tmp_path / "project"
    project.mkdir()
    ExperimentVersionControl.init(project, workspace=True)
    recorder = RunRecorder(project, pipeline="stats", author=AUTHOR)

    def _explode(drug):  # run-level failure before the subject loop
        raise MemoryError("simulated run-level failure")

    monkeypatch.setattr(stats_mod, "PopulationCorrelationCollector", _explode)
    with pytest.raises(MemoryError):
        _run_stats(project, monkeypatch, _StubScatterEngine, recorder=recorder)

    evc = ExperimentVersionControl.open(project)
    assert [r.message for r in evc.history()] == ["run approved: stats"]
    failures = [e for e in evc.recover() if e.op == "run-failed"]
    assert len(failures) == 1 and "MemoryError" in failures[0].message


def test_recorder_none_is_a_true_no_op(tmp_path, monkeypatch):
    """The off switch: with recorder=None (the default) a run performs zero
    .evc reads/writes and produces the same outputs as before Phase 3."""
    project = tmp_path / "project"
    project.mkdir()
    log = _run_stats(project, monkeypatch, _StubScatterEngine, recorder=None)
    assert not list(project.rglob(".evc"))
    assert not (project / "results").exists()
    assert not (project / "parameters").exists()
    assert "evc_pre_revision" not in log and "evc_post_revision" not in log
    assert set(log) == {
        "run_timestamp", "analyses_requested", "subjects_requested",
        "lab_config_path", "stats_config_path", "params", "completed", "skipped",
        "output_failures",
    }
    assert log["completed"] == [{"line_num": 97, "analysis": "scatter_correlation"}]


# -- lab_config run.history + cli gating --------------------------------------


def test_run_config_history_parses_and_defaults_false(tmp_path):
    from aceneurotools.config.lab_config import LabConfig

    config = {
        "primary_channel": "CBvsPCEEG",
        "freq_range": [0.5, 4.0],
        "conditions": {"drugA": {"subjects": [97], "is_drug": True}},
        "time_windows": {"97": [[0, 30], [30, 60]]},
        "run": {"mode": "stats", "history": True},
    }
    path = tmp_path / "lab_config.json"
    path.write_text(json.dumps(config))
    assert LabConfig.from_json(path).run.history is True

    config["run"] = {"mode": "stats"}
    path.write_text(json.dumps(config))
    assert LabConfig.from_json(path).run.history is False


def test_cli_history_recorder_gating(tmp_path):
    from aceneurotools.cli import _history_recorder
    from aceneurotools.config.lab_config import ConditionSpec, LabConfig, RunConfig

    def lab(history: bool) -> LabConfig:
        return LabConfig(
            primary_channel="CBvsPCEEG",
            freq_range=[0.5, 4.0],
            conditions={"drugA": ConditionSpec(subjects=[97], is_drug=True)},
            time_windows={97: [[0.0, 30.0], [30.0, 60.0]]},
            run=RunConfig(mode="stats", history=history),
        )

    project = tmp_path / "project"
    project.mkdir()
    # history off → None even if tracked
    ExperimentVersionControl.init(project, workspace=True)
    assert _history_recorder(lab(False), project, "stats", None) is None
    # history on + tracked → recorder (line label from lab config subjects)
    recorder = _history_recorder(lab(True), project, "stats", None)
    assert isinstance(recorder, RunRecorder) and recorder.line == "97"
    # history on but untracked → None
    untracked = tmp_path / "untracked"
    untracked.mkdir()
    assert _history_recorder(lab(True), untracked, "stats", None) is None
