"""Differential tests against real CLI/Python entry points, never GUI-derived oracles."""

import base64
import csv
import inspect
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

import cv2
import numpy as np
import pytest
from gui.box_setup import BoxSetup
from gui.csv_projects import Project
from gui.run_specs import effective_parameters
from gui.server import ProjectServer

from aceneurotools.config import config_utils
from tests.test_gui_analysis import make_recording

ROOT = Path(__file__).resolve().parents[1]
PROBE = Path(__file__).with_name("parity_probe.py")


def environment():
    return {
        **os.environ,
        "PYTHONPATH": str(Path(config_utils.__file__).resolve().parents[2]),
        "MPLBACKEND": "Agg",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def write_settings(root, values):
    values = {"unknown_lab_column": "preserve", **values}
    with (root / "analysis_parameters.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["line number", *values])
        writer.writeheader()
        writer.writerow({"line number": "1", **values})


def cli_parameters(root, kind):
    capture = root / "cli-parameters.json"
    completed = subprocess.run(
        [sys.executable, str(PROBE), "parameters", kind, str(root), str(capture)],
        env=environment(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(capture.read_text())


def gui_parameters(root, kind):
    if kind == "miniscope":
        from aceneurotools.pipelines.miniscope import MiniscopePipeline

        method = MiniscopePipeline.run
    elif kind == "ephys":
        from aceneurotools.pipelines.ephys import EphysPipeline

        method = EphysPipeline.run
    else:
        from aceneurotools.pipelines.multimodal import MultimodalPipeline

        method = MultimodalPipeline.run
    raw = Project.open(root).inspect("1")["parameters"]
    options, _ = effective_parameters(kind, raw)
    bound = inspect.signature(method).bind_partial(
        None, **options, line_num=1, project_path=str(root), data_path=str(root), headless=True
    )
    bound.apply_defaults()
    return json.loads(json.dumps({key: value for key, value in bound.arguments.items() if key != "self"}))


@pytest.fixture
def project_folder(tmp_path):
    (tmp_path / "experiments.csv").write_text("line number,id\n1,Parity subject\n")
    return tmp_path


@pytest.mark.parametrize(
    "kind,settings",
    [
        ("miniscope", {}),
        ("ephys", {}),
        ("multimodal", {}),
        (
            "miniscope",
            {
                "n_processes": "3",
                "filenames": "['0.avi', '2.avi']",
                "df_over_f": "True",
                "secs_window": "7.5",
                "quantile_min": "12",
                "method": "delta_f_over_f",
                "detrend_method": "linear",
                "run_CNMFE": "False",
                "parallel": "False",
                "apply_motion_correction": "False",
                "filter_data": "False",
                "spectrogram": "False",
                "inline": "False",
                "n": "3",
                "cut": "[0.2, 1.3]",
                "window_length": "10",
                "window_step": "2",
                "freq_lims": "[0, 4]",
                "crop_coords": "(2, 3, 20, 15)",
                "find_calcium_events": "False",
                "compute_miniscope_phase": "False",
                "inspect_motion_correction": "True",
                "remove_components_with_gui": "True",
                "plot_params": "True",
                "save_estimates": "False",
                "save_CNMFE_params": "False",
                "event_height": "3.5",
                "derivative_for_estimates": "second",
                "save_CNMFE_estimates_filename": "parity.hdf5",
            },
        ),
        (
            "ephys",
            {
                "channel_name": "RHS2116_AC_0",
                "remove_artifacts": "True",
                "filter_type": "butter",
                "filter_range": "[0.5, 4]",
                "compute_phases": "True",
                "plot_channel": "True",
                "plot_spectrogram": "True",
                "plot_phases": "True",
                "logging_level": "WARNING",
                "crop_coords": "(2,3,20,15)",
                "unknown_lab_column": "keep",
            },
        ),
        (
            "multimodal",
            {
                "channel_name": "RHS2116_AC_0",
                "miniscope_filenames": "['0.avi']",
                "crop": "False",
                "run_CNMFE": "False",
                "delete_TTLs": "False",
                "fix_TTL_gaps": "False",
                "only_experiment_events": "True",
                "all_TTL_events": "False",
                "ca_events": "False",
                "time_range": "[1.0, 5.0]",
                "filter_range": "[0.5, 4]",
            },
        ),
        (
            "miniscope",
            {
                "n_processes": "",
                "filenames": "",
                "cut": "None",
                "inline": "nan",
                "crop_coords": "",
                "window_step": "NA",
                "event_height": "NULL",
                "btype": "N/A",
            },
        ),
    ],
)
def test_saved_csv_settings_match_real_headless_cli(project_folder, kind, settings):
    write_settings(project_folder, settings)
    assert gui_parameters(project_folder, kind) == cli_parameters(project_folder, kind)


@pytest.mark.parametrize(
    "settings",
    [
        {"crop": "False"},
        {"crop": "(2, 3, 20, 15)"},
        {"filter_miniscope_data": "False"},
        {"compute_miniscope_spectrogram": "False"},
        {"df_over_f_method": "delta_f_over_f"},
        {"filter_data": "True", "filter_miniscope_data": "False"},
    ],
)
def test_gui_saved_run_flags_match_cli(project_folder, settings):
    """Strict checks: failures are real parity gaps, never expected-failure skips."""
    write_settings(project_folder, settings)
    assert gui_parameters(project_folder, "miniscope") == cli_parameters(project_folder, "miniscope")


def subprocess_ok(command, *, cwd=None, extra_env=None):
    result = subprocess.run(
        command, cwd=cwd, env={**environment(), **(extra_env or {})}, capture_output=True, text=True, timeout=90
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def http(base, route, body=None):
    request = Request(
        base + route,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response)


@pytest.fixture
def app(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    server = ProjectServer(("127.0.0.1", 0), box_setup=BoxSetup(tmp_path / "box-settings"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield root, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def open_experiment(base, root):
    project = http(base, "/api/projects/open", {"path": str(root)})
    detail = http(base, f"/api/experiment?project={project['id']}&number=1")
    return {"project": project["id"], "number": "1", "versions": detail["versions"], "data_path": str(root)}


@pytest.mark.parametrize(
    "kind,changes",
    [
        ("miniscope", {"n_processes": "2", "inline": "False", "run_CNMFE": "True"}),
        ("ephys", {"channel_name": "RHS2116_AC_0", "filter_range": "[0.5, 4]", "compute_phases": "True"}),
    ],
)
def test_gui_http_saved_settings_match_real_cli(app, kind, changes):
    root, base = app
    (root / "experiments.csv").write_text("line number,id\n1,Parity subject\n")
    write_settings(root, {})
    payload = open_experiment(base, root)
    saved = http(base, "/api/run/settings/save", {**payload, "kind": kind, "changes": changes})
    shown = http(base, f"/api/run/settings?project={payload['project']}&number=1&kind={kind}")
    assert {key: saved["experiment"]["parameters"][key] for key in changes} == changes
    assert all(shown["sources"][key] == "Saved CSV" for key in changes)
    if kind == "miniscope":
        from aceneurotools.pipelines.miniscope import MiniscopePipeline

        method = MiniscopePipeline.run
    else:
        from aceneurotools.pipelines.ephys import EphysPipeline

        method = EphysPipeline.run
    bound = inspect.signature(method).bind_partial(
        None, **shown["parameters"], line_num=1, project_path=str(root), data_path=str(root), headless=True
    )
    bound.apply_defaults()
    actual = json.loads(json.dumps({key: value for key, value in bound.arguments.items() if key != "self"}))
    assert actual == cli_parameters(root, kind)


def gui_run(base, payload, kind):
    review = http(base, "/api/run/review", {**payload, "kind": kind})
    assert review["blockers"] == []
    run = http(base, "/api/run/start", {**payload, "review": review["review"], "confirmed": True})
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = http(base, f"/api/run?project={payload['project']}&run={run['id']}")
        if result["state"] != "running":
            assert result["state"] == "completed", result["log"]
            return Path(result["directory"])
        time.sleep(0.1)
    http(base, "/api/run/stop", {**payload, "run": run["id"]})
    pytest.fail("Parity fixture analysis exceeded 90 seconds.")


def cluster_run(base, payload, kind, root, folder, *, slurm=False, cpus=1):
    folder.mkdir()
    output = folder / "outputs"
    result = http(
        base,
        "/api/job/scripts",
        {
            **payload,
            "kind": kind,
            "cluster": {
                "recording_path": str(root / "raw"),
                "output_path": str(output),
                "python": sys.executable,
                "cpus": str(cpus),
                "memory_gb": "1",
                "time": "00:05:00",
            },
        },
    )
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(result["archive"]))) as archive:
        archive.extractall(folder)
    # PYTHONPATH contains only core src: the GUI worker must come from the ZIP.
    command = ["bash", "submit.slurm"] if slurm else [sys.executable, "run_job.py"]
    subprocess_ok(
        command,
        cwd=folder,
        extra_env={"SLURM_SUBMIT_DIR": str(folder), "SLURM_CPUS_PER_TASK": str(cpus)} if slurm else {},
    )
    runs = list(output.iterdir())
    assert len(runs) == 1 and json.loads((runs[0] / "outcome.json").read_text())["success"] is True
    return runs[0]


def arrays(path):
    with np.load(path, allow_pickle=False) as archive:
        return dict(archive)


@pytest.mark.parametrize("coords", [None, (2, 3, 20, 15)])
def test_real_mean_fluorescence_matches_python_gui_and_cluster(app, tmp_path, coords):
    root, base = app
    _, frames = make_recording(root)
    write_settings(root, {"crop": str(coords is not None), "crop_coords": str(coords) if coords else ""})
    before = {name: (root / name).read_bytes() for name in ["experiments.csv", "analysis_parameters.csv", "raw/0.avi"]}
    (root / "api-options.json").write_text("{}")
    api = tmp_path / "api.npz"
    subprocess_ok([sys.executable, str(PROBE), "api", "compute", str(root), str(api)])
    config = root / "lab_config.json"
    config.write_text(
        json.dumps(
            {
                "primary_channel": "EEG",
                "freq_range": [0.5, 4],
                "conditions": {"control": {"subjects": [1], "is_drug": False}},
                "time_windows": {"1": [[0, 0.5], [0.5, 1]]},
            }
        )
    )
    cli_output = tmp_path / "cli-output"
    subprocess_ok(
        [
            sys.executable,
            "-m",
            "aceneurotools.pipelines.compute",
            "--project-path",
            str(root),
            "--data-path",
            str(root),
            "--lab-config",
            str(config),
            "--calcium-signal-dir",
            str(cli_output),
            "--line-nums",
            "1",
            "--headless",
            "--verbose",
        ]
    )
    payload = open_experiment(base, root)
    local = gui_run(base, payload, "compute")
    cluster = cluster_run(base, payload, "compute", root, tmp_path / "cluster")
    slurm = cluster_run(base, payload, "compute", root, tmp_path / "slurm", slurm=True)
    values = np.asarray(frames)
    if coords:
        values = values[:, 24 - 15 : 24 - 3, 2:20]
    expected = values.mean(axis=(1, 2))
    for path in [
        api,
        cli_output / "meanFluorescence_1.npz",
        *[folder / "calcium_signals/meanFluorescence_1.npz" for folder in [local, cluster, slurm]],
    ]:
        np.testing.assert_allclose(arrays(path)["meanFluorescence"], expected, rtol=0, atol=0)
    assert all((root / name).read_bytes() == value for name, value in before.items())


def test_real_ephys_filter_phase_and_timing_match_python_cli_gui_and_cluster(app, tmp_path):
    root, base = app
    raw = root / "raw"
    raw.mkdir()
    count, rate, clock_rate = 600, 30, 30000
    (raw / "start-time_0.csv").write_text(f"2024-01-01T00:00:00,{clock_rate},1024,1024\n")
    (np.arange(count, dtype=np.uint64) * (clock_rate // rate)).tofile(raw / "rhs2116pair-clock_0.raw")
    voltage = (32768 + 1000 * np.sin(2 * np.pi * np.arange(count) / rate)).astype(np.uint16)
    np.repeat(voltage[:, None], 32, axis=1).tofile(raw / "rhs2116pair-ac_0.raw")
    (raw / "rhs2116pair-dc_0.raw").write_bytes(b"\0" * 16)
    (root / "experiments.csv").write_text(
        "line number,id,ephys directory,calcium imaging directory,Box ephys folder ID,Box Calcium Folder ID\n1,Parity,raw,,,\n"
    )
    options = {
        "channel_name": "RHS2116_AC_0",
        "filter_type": "butter",
        "filter_range": [0.5, 4],
        "compute_phases": True,
        "logging_level": "WARNING",
    }
    write_settings(root, {key: str(value) for key, value in options.items()})
    (root / "api-options.json").write_text(json.dumps(options))
    api, cli = tmp_path / "api.npz", tmp_path / "cli.npz"
    subprocess_ok([sys.executable, str(PROBE), "api", "ephys", str(root), str(api)])
    subprocess_ok([sys.executable, str(PROBE), "cli", "ephys", str(root), str(cli)])
    payload = open_experiment(base, root)
    local = gui_run(base, payload, "ephys")
    cluster = cluster_run(base, payload, "ephys", root, tmp_path / "cluster")
    reference = arrays(api)
    assert set(reference) == {"signal", "time", "sampling_rate", "signal_filtered", "phases"}
    assert reference["signal"].shape == (count,)
    np.testing.assert_allclose(reference["time"], np.arange(count) / rate, rtol=0, atol=0)
    assert reference["sampling_rate"] == pytest.approx(rate)
    assert not np.allclose(reference["signal_filtered"], reference["signal"])
    for path in [cli, local / "ephys.npz", cluster / "ephys.npz"]:
        actual = arrays(path)
        assert actual.keys() == reference.keys()
        for key in reference:
            np.testing.assert_allclose(actual[key], reference[key], rtol=0, atol=0, err_msg=key)


def decoded_movie(path):
    capture = cv2.VideoCapture(str(path))
    values = []
    try:
        assert capture.isOpened(), path
        while True:
            ok, image = capture.read()
            if not ok:
                break
            values.append(image)
    finally:
        capture.release()
    assert values, path
    return np.asarray(values)


@pytest.mark.parametrize("normalize", [False, True])
def test_real_preprocessing_pixels_projections_and_timestamps_match_python_gui_and_cluster(app, tmp_path, normalize):
    root, base = app
    make_recording(root)
    options = {
        "crop": True,
        "crop_coords": [2, 3, 20, 15],
        "filenames": ["0.avi"],
        "df_over_f": normalize,
        "secs_window": 1,
        "quantile_min": 8,
        "df_over_f_method": "delta_f_over_f",
    }
    write_settings(root, {key: str(value) for key, value in options.items()})
    (root / "api-options.json").write_text(json.dumps(options))
    api = tmp_path / "api.npz"
    subprocess_ok([sys.executable, str(PROBE), "api", "preprocess", str(root), str(api)])
    reference_file = next((root / "raw/saved_movies").glob("preprocessed*.avi"))
    reference_pixels = decoded_movie(reference_file)
    assert reference_pixels.shape == (20, 12, 18, 3)
    payload = open_experiment(base, root)
    local = gui_run(base, payload, "preprocess")
    cluster = cluster_run(base, payload, "preprocess", root, tmp_path / "cluster")
    reference = arrays(api)
    for folder in [local, cluster]:
        actual_file = next((folder / "recording/saved_movies").glob("preprocessed*.avi"))
        np.testing.assert_array_equal(decoded_movie(actual_file), reference_pixels)
        actual = arrays(folder / "preprocessing.npz")
        assert actual.keys() == reference.keys() - {"movie"}
        for key in actual:
            np.testing.assert_allclose(actual[key], reference[key], rtol=0, atol=0, err_msg=key)


def make_cnmfe_recording(root, workers=1):
    raw = root / "raw"
    raw.mkdir()
    size, count, rate = 40, 200, 10
    y, x = np.mgrid[:size, :size]
    footprints = [np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / 8) for cx, cy in [(12, 12), (28, 27)]]
    rng = np.random.default_rng(1234)
    writer = cv2.VideoWriter(str(raw / "0.avi"), cv2.VideoWriter_fourcc(*"FFV1"), rate, (size, size), False)
    assert writer.isOpened()
    for index in range(count):
        image = 30 + rng.normal(0, 0.8, (size, size))
        for cell, footprint in enumerate(footprints):
            event = (index + cell * 13) % 50
            image += 100 * np.exp(-event / 8) * footprint
        writer.write(np.clip(image, 0, 255).astype(np.uint8))
    writer.release()
    (raw / "metaData.json").write_text(json.dumps({"frameRate": rate}))
    (raw / "timeStamps.csv").write_text(
        "Frame Number,Time Stamp (ms),Buffer Index\n" + "".join(f"{index},{index * 100},0\n" for index in range(count))
    )
    (root / "experiments.csv").write_text(
        "line number,id,date (YYMMDD),calcium imaging directory,Box Calcium Folder ID,ephys directory,Box ephys folder ID\n"
        "1,Parity cells,261005,raw,,,\n"
    )
    options = {
        "filenames": ["0.avi"],
        "crop": True,
        "crop_coords": [0, 0, size, size],
        "detrend_method": None,
        "df_over_f": False,
        "parallel": workers > 1,
        "n_processes": workers,
        "apply_motion_correction": False,
        "inspect_motion_correction": False,
        "plot_params": False,
        "run_CNMFE": True,
        "save_estimates": True,
        "save_CNMFE_params": True,
        "remove_components_with_gui": False,
        "find_calcium_events": True,
        "derivative_for_estimates": "zeroth",
        "event_height": 5,
        "filter_miniscope_data": True,
        "compute_miniscope_phase": True,
        "compute_miniscope_spectrogram": True,
        "inline": False,
        "cut": [0.1, 1.5],
        "window_length": 5,
        "window_step": 2,
        "freq_lims": [0, 4],
    }
    caiman = {
        "method_init": "corr_pnr",
        "gSig": [2, 2],
        "gSiz": [7, 7],
        "min_corr": 0.5,
        "min_pnr": 3,
        "rf": None,
        "stride": 6,
        "nb": 0,
        "nb_patch": 0,
        "p": 1,
        "ring_size_factor": 1.5,
        "use_cnn": False,
        "normalize_init": False,
        "center_psf": True,
    }
    caiman.update(ssub=1, tsub=1)
    write_settings(root, {key: str(value) for key, value in {**options, **caiman}.items()})
    (root / "api-options.json").write_text(json.dumps(options))


@pytest.mark.integration
@pytest.mark.parametrize("workers", [1, 2])
def test_real_cnmfe_traces_footprints_events_filters_and_spectra_match_all_entry_points(app, tmp_path, workers):
    root, base = app
    make_cnmfe_recording(root, workers)
    originals = {
        name: (root / name).read_bytes() for name in ["experiments.csv", "analysis_parameters.csv", "raw/0.avi"]
    }
    # Separate input copies keep direct API/CLI crop writeback from altering the
    # GUI's inputs or letting one route reuse another route's scientific outputs.
    references = []
    for mode in ["api", "configs", "cli"]:
        project = tmp_path / f"{mode}-project"
        shutil.copytree(root, project)
        output = tmp_path / f"{mode}.npz"
        subprocess_ok([sys.executable, str(PROBE), mode, "miniscope", str(project), str(output)])
        references.append(output)
    expected = arrays(references[0])
    expected_diagnostics = arrays(references[0].with_suffix(".diagnostics.npz"))
    assert expected["C"].shape[0] >= 2 and expected["C"].shape[1] == 200
    assert expected["A_dense"].shape == (1600, expected["C"].shape[0])
    assert np.isfinite(expected["PSD_spect"]).all()
    events = json.loads(references[0].with_suffix(".events.json").read_text())
    assert any(events.values()), "The fixture must exercise actual calcium-event detection."
    for path in references[1:]:
        actual = arrays(path)
        assert actual.keys() == expected.keys()
        for key in expected:
            np.testing.assert_allclose(actual[key], expected[key], rtol=1e-5, atol=1e-6, err_msg=key)
        assert json.loads(path.with_suffix(".events.json").read_text()) == events
    payload = open_experiment(base, root)
    local = gui_run(base, payload, "miniscope")
    cluster = cluster_run(base, payload, "miniscope", root, tmp_path / "cluster", cpus=workers)
    from caiman.source_extraction.cnmf.cnmf import load_CNMF
    from scipy.sparse import csc_matrix

    for folder in [local, cluster]:
        actual = arrays(folder / "postprocessing.npz")
        for key in expected.keys() - {"A_dense"}:
            np.testing.assert_allclose(actual[key], expected[key], rtol=1e-5, atol=1e-6, err_msg=key)
        components = arrays(folder / "components.npz")
        matrix = csc_matrix(
            (components["A_data"], components["A_indices"], components["A_indptr"]), shape=tuple(components["A_shape"])
        )
        np.testing.assert_allclose(matrix.toarray(), expected["A_dense"], rtol=1e-5, atol=1e-6)
        assert json.loads((folder / "calcium-events.json").read_text())["ca_events_idx"] == events
        saved = load_CNMF(str(folder / "recording/saved_movies/estimates.hdf5")).estimates
        np.testing.assert_allclose(saved.C, expected["C"], rtol=1e-5, atol=1e-6)
        np.testing.assert_allclose(saved.A.toarray(), expected["A_dense"], rtol=1e-5, atol=1e-6)
        diagnostics = arrays(folder / "diagnostics.npz")
        for key, value in expected_diagnostics.items():
            np.testing.assert_allclose(diagnostics[key], value, rtol=1e-5, atol=1e-6, err_msg=key)
    assert all((root / name).read_bytes() == value for name, value in originals.items())
