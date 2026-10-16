import csv
import inspect
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from aceneurotools.gui.csv_projects import Project
from aceneurotools.gui.run_specs import effective_parameters
from aceneurotools.gui.server import ProjectServer
from aceneurotools.shared import config_utils
from tests.test_gui_server import TOKENS

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


def http(base, route, body=None):
    request = Request(
        base + route,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": "Bearer " + TOKENS[base],
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response)


@pytest.fixture
def app(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    server = ProjectServer(
        ("127.0.0.1", 0),
    )
    TOKENS[f"http://127.0.0.1:{server.server_address[1]}"] = server.token
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
        (
            "multimodal",
            {
                "channel_name": "RHS2116_AC_0",
                "miniscope_filenames": "['0.avi']",
                "ca_events": "True",
                "fix_TTL_gaps": "True",
                "time_range": "[1.0, 5.0]",
            },
        ),
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
    elif kind == "ephys":
        from aceneurotools.pipelines.ephys import EphysPipeline

        method = EphysPipeline.run
    else:
        from aceneurotools.pipelines.multimodal import MultimodalPipeline

        method = MultimodalPipeline.run
    bound = inspect.signature(method).bind_partial(
        None, **shown["parameters"], line_num=1, project_path=str(root), data_path=str(root), headless=True
    )
    bound.apply_defaults()
    actual = json.loads(json.dumps({key: value for key, value in bound.arguments.items() if key != "self"}))
    assert actual == cli_parameters(root, kind)
