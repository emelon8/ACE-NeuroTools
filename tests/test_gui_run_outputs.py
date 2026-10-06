"""Exercise the actual worker export boundary without expensive CNMF fitting."""

import json
from types import SimpleNamespace

import numpy as np
import pytest
from gui.run_outputs import OutputInventory, ephys_outputs
from gui.run_worker import execute
from gui.runs import inventory

from tests.test_gui_analysis import make_recording


@pytest.fixture
def worker_case(tmp_path, monkeypatch):
    from aceneurotools.pipelines import miniscope

    project, _ = make_recording(tmp_path)
    root = project / "run"
    root.mkdir()
    for name in ["experiments.csv", "analysis_parameters.csv"]:
        (root / name).write_bytes((project / name).read_bytes())
    raw = np.arange(20, dtype=float)
    filtered = raw / 2
    estimates = SimpleNamespace(
        C=np.ones((2, 20)),
        SNR_comp=np.array([4.0, 6.0]),
        r_values=None,
        cnn_preds=None,
        idx_components=np.array([1]),
        idx_components_bad=np.array([0]),
    )
    from scipy.sparse import csc_matrix

    estimates.A = csc_matrix(np.arange(8).reshape(4, 2))
    dm = SimpleNamespace(
        CNMFE_obj=SimpleNamespace(estimates=estimates),
        fr=10.0,
        time_stamps=raw / 10,
        projections=SimpleNamespace(
            time=filtered, **{name: np.ones((2, 2)) for name in ["max", "std", "min", "mean", "median", "range"]}
        ),
        ca_events_idx={0: np.array([3, 8]), 1: np.array([], dtype=int)},
        filter_object=SimpleNamespace(data=raw, filtered_data=filtered),
        PSD_spect=np.ones((2, 3)),
        t_spect=np.arange(3),
        freqs_spect=np.arange(2),
        p_spect=np.ones((2, 3)),
        miniscope_phases=np.arange(20),
        estimates_filepath=None,
        opts_caiman_filepath=None,
        preprocessed_movie_filepath=None,
        motion_corrected_movie_filepath=None,
    )

    class Pipeline:
        def run(self, **params):
            self.miniscope_data_manager = dm

    monkeypatch.setattr(miniscope, "MiniscopePipeline", Pipeline)
    manifest = dict(
        directory=str(root),
        recording_path=str(project / "raw"),
        files=inventory(project / "raw"),
        recording_column="calcium imaging directory",
        number="1",
        kind="miniscope",
        parameters={
            "crop": False,
            "inline": True,
            "find_calcium_events": True,
            "filter_miniscope_data": True,
            "compute_miniscope_spectrogram": True,
            "compute_miniscope_phase": True,
        },
    )
    return root, manifest, dm


def test_worker_exports_events_ids_filtered_signals_and_diagnostics(worker_case):
    root, manifest, dm = worker_case
    execute(manifest)
    events = json.loads((root / "calcium-events.json").read_text())
    assert events["ca_events_idx"] == {"0": [3, 8], "1": []}
    assert events["neuron_ids"] == [0, 1]
    with np.load(root / "postprocessing.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["neuron_ids"], [0, 1])
        np.testing.assert_array_equal(saved["temporal_projection"], dm.projections.time)
        np.testing.assert_array_equal(saved["unfiltered_temporal_projection"], dm.filter_object.data)
        np.testing.assert_array_equal(saved["filtered_temporal_projection"], dm.filter_object.filtered_data)
        np.testing.assert_array_equal(saved["C"], dm.CNMFE_obj.estimates.C)
    with np.load(root / "diagnostics.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["SNR_comp"], [4, 6])
        np.testing.assert_array_equal(saved["idx_components"], [1])
    with np.load(root / "components.npz", allow_pickle=False) as saved:
        from scipy.sparse import csc_matrix

        A = csc_matrix((saved["A_data"], saved["A_indices"], saved["A_indptr"]), shape=tuple(saved["A_shape"]))
        np.testing.assert_array_equal(A.toarray(), dm.CNMFE_obj.estimates.A.toarray())
    report = json.loads((root / "output-inventory.json").read_text())
    entries = {item["name"]: item for item in report["outputs"]}
    assert entries["ca_events_idx"]["status"] == "exported"
    assert entries["SNR_comp"]["file"] == "diagnostics.npz"
    assert entries["r_values"]["status"] == "not_computed"
    assert entries["filtered_temporal_projection"]["status"] == "exported"
    assert report["parameters"]["inline"] is True
    for entry in report["outputs"]:
        if entry["status"] == "exported":
            assert (root / entry["file"]).is_file()
            if entry["file"].endswith(".npz"):
                with np.load(root / entry["file"], allow_pickle=False) as saved:
                    assert entry["key"] in saved


def test_disabled_outputs_are_explicit_in_inventory(worker_case):
    root, manifest, dm = worker_case
    manifest["parameters"].update(
        find_calcium_events=False,
        filter_miniscope_data=False,
        compute_miniscope_spectrogram=False,
        compute_miniscope_phase=False,
    )
    dm.ca_events_idx = dm.filter_object = dm.miniscope_phases = None
    dm.PSD_spect = dm.t_spect = dm.freqs_spect = dm.p_spect = None
    execute(manifest)
    report = json.loads((root / "output-inventory.json").read_text())
    entries = {item["name"]: item for item in report["outputs"]}
    for name in ["ca_events_idx", "filtered_temporal_projection", "PSD_spect", "miniscope_phases"]:
        assert entries[name]["status"] == "not_computed" and "disabled" in entries[name]["reason"]
    assert not (root / "calcium-events.json").exists()


def test_ephys_export_preserves_events_filters_and_inventory(tmp_path):
    channel = SimpleNamespace(
        name="EEG",
        signal=np.arange(8),
        time_vector=np.arange(8) / 10,
        sampling_rate=10.0,
        signal_filtered=np.arange(8) / 2,
        phases=None,
        events={"labels": np.array(["injection"]), "timestamps": np.array([0.5])},
    )
    report = OutputInventory(tmp_path, "ephys", {"compute_phases": False})
    ephys_outputs(report, channel)
    report.finish()
    assert json.loads((tmp_path / "ephys-events.json").read_text()) == {"labels": ["injection"], "timestamps": [0.5]}
    with np.load(tmp_path / "ephys.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["signal_filtered"], channel.signal_filtered)
    outputs = {item["name"]: item for item in json.loads((tmp_path / "output-inventory.json").read_text())["outputs"]}
    assert outputs["phases"]["reason"] == "compute_phases disabled"
    assert outputs["ephys_events"]["status"] == "exported"


def test_worker_does_not_silently_drop_unserializable_numeric_output(worker_case):
    root, manifest, dm = worker_case
    dm.PSD_spect = {"unexpected": np.ones(3)}
    with pytest.raises(ValueError, match="PSD_spect"):
        execute(manifest)
