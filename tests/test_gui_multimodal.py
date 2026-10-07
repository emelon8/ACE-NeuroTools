"""Multimodal GUI staging, export, and the core event-phase prerequisite."""

import csv
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from gui.csv_projects import Project, ProjectError
from gui.run_outputs import OutputInventory, multimodal_outputs
from gui.run_worker import execute
from gui.runs import Runs
from tests.test_gui_analysis import make_recording
from tests.test_gui_parity import app, http, open_experiment


def project_with_two_recordings(root):
    make_recording(root)
    ephys = root / "ephys"
    ephys.mkdir()
    (ephys / "signal.raw").write_bytes(b"ephys samples")
    (root / "experiments.csv").write_text(
        "line number,id,calcium imaging directory,ephys directory,Box Calcium Folder ID,Box ephys folder ID\n"
        "1,Combined,raw,ephys,,\n"
    )
    (root / "analysis_parameters.csv").write_text(
        "line number,crop,run_CNMFE,ca_events,miniscope_filenames\n1,False,False,False,\"['0.avi']\"\n"
    )
    return Project.open(root)


def test_review_requires_and_tracks_both_recordings(tmp_path):
    project = project_with_two_recordings(tmp_path)
    runs = Runs()
    body = {"project": project.id, "number": "1", "versions": project.digests, "kind": "multimodal"}
    review = runs.review(project, body)
    assert review["blockers"] == []
    assert Path(review["recording_path"]) == tmp_path / "raw"
    assert Path(review["ephys_recording_path"]) == tmp_path / "ephys"
    assert {item["path"] for item in review["ephys_files"]} == {"signal.raw"}
    assert review["input_bytes"] == sum(item["size"] for item in review["files"] + review["ephys_files"])
    assert "Aligned timing and phases" in review["destinations"]
    (tmp_path / "ephys/signal.raw").write_bytes(b"changed")
    with pytest.raises(ProjectError, match="Electrophysiology files changed"):
        runs.start(project, {**body, "review": review["review"], "confirmed": True})


def test_multimodal_settings_and_review_are_available_over_gui_http(app):
    root, base = app
    project_with_two_recordings(root)
    payload = open_experiment(base, root)
    settings = http(base, f"/api/run/settings?project={payload['project']}&number=1&kind=multimodal")
    assert "miniscope_filenames" in settings["parameters"]
    assert "fix_TTL_gaps" in settings["parameters"]
    review = http(base, "/api/run/review", {**payload, "kind": "multimodal"})
    assert review["blockers"] == []
    assert review["ephys_files"][0]["path"] == "signal.raw"


def test_worker_stages_both_recordings_and_calls_multimodal_pipeline(tmp_path, monkeypatch):
    project = project_with_two_recordings(tmp_path)
    run = tmp_path / "run"
    run.mkdir()
    for name in ("experiments.csv", "analysis_parameters.csv"):
        (run / name).write_bytes((tmp_path / name).read_bytes())
    review = Runs().review(project, {"project": project.id, "number": "1", "versions": project.digests,
                                   "kind": "multimodal"})
    seen = {}

    class Pipeline:
        def run(self, **params):
            seen.update(params)
            row = next(csv.DictReader((Path(params["project_path"]) / "experiments.csv").open()))
            assert row["calcium imaging directory"] == "recording"
            assert row["ephys directory"] == "recording-ephys"
            assert (Path(params["data_path"]) / "recording/0.avi").is_file()
            assert (Path(params["data_path"]) / "recording-ephys/signal.raw").read_bytes() == b"ephys samples"

    fake = types.ModuleType("aceneurotools.pipelines.multimodal")
    fake.MultimodalPipeline = Pipeline
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    monkeypatch.setattr("gui.run_worker.multimodal_outputs", lambda report, pipeline: report.array(
        "aligned_frames", np.arange(2), "alignment.npz"))
    execute({**review, "directory": str(run)})
    assert seen["headless"] is True and seen["line_num"] == 1
    with np.load(run / "alignment.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["aligned_frames"], [0, 1])
    assert (tmp_path / "ephys/signal.raw").read_bytes() == b"ephys samples"


def test_multimodal_export_keeps_alignment_arrays_and_per_neuron_events(tmp_path, monkeypatch):
    from gui import run_outputs

    called = []
    monkeypatch.setattr(run_outputs, "miniscope_outputs", lambda report, manager: called.append("miniscope"))
    monkeypatch.setattr(run_outputs, "ephys_outputs", lambda report, channel: called.append("ephys"))
    pipeline = SimpleNamespace(
        miniscope_pipeline=SimpleNamespace(miniscope_data_manager=object()),
        ephys_pipeline=SimpleNamespace(ephys_data_manager=SimpleNamespace(get_channel=lambda name: object())),
        t_ca_im=np.array([0.1, 0.2]), low_confidence_periods=np.empty((0, 2), dtype=int),
        ephys_idx_all_TTL_events=np.array([3, 6]), ca_frame_num_of_ephys_idx=np.array([0, 1]),
        phase_hist_ephys=np.array([2, 1]), phase_bin_edges_ephys=np.array([-1, 0, 1]),
        phase_hist_miniscope=np.array([1, 2]), phase_bin_edges_miniscope=np.array([-1, 0, 1]),
        ephys_idx_ca_events={0: np.array([6])},
        ca_events_phases_ephys={0: np.array([0.5])},
        ca_events_phases_miniscope={0: np.array([-0.5])},
    )
    report = OutputInventory(tmp_path, "multimodal", {"channel_name": "EEG", "ca_events": True})
    multimodal_outputs(report, pipeline)
    report.finish()
    assert called == ["miniscope", "ephys"]
    with np.load(tmp_path / "alignment.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["t_ca_im"], [0.1, 0.2])
        np.testing.assert_array_equal(saved["ephys_idx_all_TTL_events"], [3, 6])
    assert json.loads((tmp_path / "ephys_idx_ca_events.json").read_text()) == {"0": [6]}
    assert json.loads((tmp_path / "ca_events_phases_ephys.json").read_text()) == {"0": [0.5]}


@pytest.mark.integration
def test_real_subpipelines_match_direct_python_and_gui_worker_with_matched_sync(tmp_path, monkeypatch):
    """Exercise both scientific loaders; substitute only absent hardware TTLs."""
    from aceneurotools.pipelines import multimodal

    caiman_temp = tmp_path / "caiman-temp"
    caiman_temp.mkdir()
    monkeypatch.setenv("CAIMAN_TEMP", str(caiman_temp))

    project = project_with_two_recordings(tmp_path)
    ephys = tmp_path / "ephys"
    (ephys / "signal.raw").unlink()
    count, rate, clock_rate = 600, 30, 30000
    (ephys / "start-time_0.csv").write_text(f"2024-01-01T00:00:00,{clock_rate},1024,1024\n")
    (np.arange(count, dtype=np.uint64) * (clock_rate // rate)).tofile(ephys / "rhs2116pair-clock_0.raw")
    voltage = (32768 + 1000 * np.sin(2 * np.pi * np.arange(count) / rate)).astype(np.uint16)
    np.repeat(voltage[:, None], 32, axis=1).tofile(ephys / "rhs2116pair-ac_0.raw")
    (ephys / "rhs2116pair-dc_0.raw").write_bytes(b"\0" * 16)
    (tmp_path / "analysis_parameters.csv").write_text(
        "line number,crop,miniscope_filenames,channel_name,run_CNMFE,ca_events,"
        "apply_motion_correction,df_over_f,detrend_method,filter_miniscope_data,"
        "compute_miniscope_phase,compute_miniscope_spectrogram,find_calcium_events,save_estimates,parallel\n"
        "1,False,\"['0.avi']\",RHS2116_AC_0,False,True,False,False,None,False,False,False,False,False,False\n"
    )
    project = Project.open(tmp_path)
    review = Runs().review(project, {"project": project.id, "number": "1", "versions": project.digests,
                                   "kind": "multimodal"})
    assert review["blockers"] == []

    def synchronized(channel, manager, ephys_manager, **kwargs):
        return np.arange(len(manager.frame_numbers)) / manager.fr, np.empty((0, 2), dtype=int), channel, manager

    monkeypatch.setattr(multimodal, "sync_neuralynx_miniscope_timestamps", synchronized)
    direct = multimodal.MultimodalPipeline()
    direct.run(**{**review["parameters"], "line_num": 1, "project_path": str(tmp_path),
                  "data_path": str(tmp_path), "headless": True})
    run = tmp_path / "multimodal-run"
    run.mkdir()
    for name in ("experiments.csv", "analysis_parameters.csv"):
        (run / name).write_bytes((tmp_path / name).read_bytes())
    execute({**review, "directory": str(run)})
    channel = direct.ephys_pipeline.ephys_data_manager.get_channel("RHS2116_AC_0")
    with np.load(run / "ephys.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["signal"], channel.signal)
        np.testing.assert_array_equal(saved["phases"], channel.phases)
    with np.load(run / "alignment.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["t_ca_im"], direct.t_ca_im)
        np.testing.assert_array_equal(saved["ephys_idx_all_TTL_events"], direct.ephys_idx_all_TTL_events)
    with np.load(run / "postprocessing.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["temporal_projection"],
                                      direct.miniscope_pipeline.miniscope_data_manager.projections.time)


@pytest.mark.parametrize("events", [False, True])
def test_multimodal_requests_ephys_phases_when_aligning_calcium_events(monkeypatch, events):
    from aceneurotools.pipelines import multimodal

    calls = []
    channel = SimpleNamespace(name="EEG", signal=np.arange(10), time_vector=np.arange(10),
                              events={}, phases=np.arange(10))

    class Ephys:
        def run(self, **params):
            calls.append(params)
            self.ephys_data_manager = SimpleNamespace(get_channel=lambda name: channel, channels={"EEG": channel})

    class Miniscope:
        def run(self, **params):
            self.miniscope_data_manager = SimpleNamespace(fr=10, ca_events_idx=None, miniscope_phases=np.arange(10))

    monkeypatch.setattr(multimodal, "EphysPipeline", Ephys)
    monkeypatch.setattr(multimodal, "MiniscopePipeline", Miniscope)
    monkeypatch.setattr(multimodal, "sync_neuralynx_miniscope_timestamps",
                        lambda channel, dm, ephys_dm, **kwargs: (np.arange(2), np.empty((0, 2)), channel, dm))
    monkeypatch.setattr(multimodal, "find_ephys_idx_of_TTL_events", lambda *args, **kwargs: (None, None))
    multimodal.MultimodalPipeline().run(line_num=1, channel_name="EEG", ca_events=events,
                                      all_TTL_events=False, headless=True)
    assert calls[0]["compute_phases"] is events
