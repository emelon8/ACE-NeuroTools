"""Verify the experiment-list activity data: Box folders, latest runs, previews, and static assets."""

import json
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import numpy as np
import pytest
from gui.cropping import preview_file, save_preview, saved_previews
from gui.csv_projects import Project
from gui.runs import Runs
from gui.server import ProjectServer
from PIL import Image


def write_project(folder):
    (folder / "experiments.csv").write_text(
        "line number,id,Box Calcium Folder ID,Box ephys folder ID\n1,R1,123456,NA\n2,R2,,987\n"
    )
    (folder / "analysis_parameters.csv").write_text("line number,crop\n1,False\n2,False\n")


def write_run(folder, run_id, number, state, **extra):
    directory = folder / ".ace-runs" / run_id
    directory.mkdir(parents=True)
    value = {"id": run_id, "number": number, "kind": "compute", "label": "Mean fluorescence", "state": state}
    value.update({"started": f"{run_id[:8]}T00:00:00+00:00", "finished": None, "parameters": {}}, **extra)
    (directory / "run.json").write_text(json.dumps(value))
    return directory


def test_summary_lists_only_numeric_box_folders(tmp_path):
    write_project(tmp_path)
    rows = {row["number"]: row for row in Project.open(str(tmp_path)).summary()["experiments"]}
    assert rows["1"]["box_folders"] == [{"name": "Calcium imaging", "id": "123456"}]
    assert rows["2"]["box_folders"] == [{"name": "Electrophysiology", "id": "987"}]


def test_latest_run_per_experiment_resolves_finished_and_untracked_runs(tmp_path):
    write_project(tmp_path)
    project = Project.open(str(tmp_path))
    write_run(tmp_path, "20261001T100000-aaaaaaaa", "1", "failed")
    finished = write_run(tmp_path, "20261002T100000-bbbbbbbb", "1", "running")
    (finished / "outcome.json").write_text(json.dumps({"success": True}))
    write_run(tmp_path, "20261003T100000-cccccccc", "2", "running")

    latest = Runs().latest(project)

    assert latest["1"]["id"] == "20261002T100000-bbbbbbbb"
    assert latest["1"]["state"] == "completed"
    assert json.loads((finished / "run.json").read_text())["state"] == "completed"
    assert latest["2"]["state"] == "untracked"
    assert Runs().latest(Project.open(str(tmp_path))) == latest


def test_preview_round_trip_handles_arbitrary_experiment_numbers(tmp_path):
    path = save_preview(tmp_path, "Example #1/2", np.arange(600 * 400, dtype=float).reshape(400, 600))
    assert path == preview_file(tmp_path, "Example #1/2") and path.parent == tmp_path / ".ace-previews"
    with Image.open(path) as image:
        assert max(image.size) == 320
    assert list(saved_previews(tmp_path)) == ["Example #1/2"]


@pytest.fixture
def server(tmp_path):
    write_project(tmp_path)
    instance = ProjectServer(("127.0.0.1", 0), str(tmp_path))
    worker = threading.Thread(target=instance.serve_forever, daemon=True)
    worker.start()
    yield f"http://127.0.0.1:{instance.server_address[1]}", tmp_path, next(iter(instance.projects))
    instance.shutdown()
    instance.server_close()
    worker.join(timeout=2)


def fetch(url):
    try:
        response = urlopen(url, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.headers.get("Content-Type"), response.read()


def test_activity_and_preview_endpoints(server):
    base, folder, project = server
    write_run(folder, "20261003T100000-cccccccc", "2", "completed")
    save_preview(folder, "1", np.eye(64))
    save_preview(folder, "removed", np.eye(64))

    status, _, body = fetch(f"{base}/api/project/activity?project={project}")
    activity = json.loads(body)
    assert status == 200
    assert activity["latest_runs"]["2"]["state"] == "completed"
    assert list(activity["previews"]) == ["1"]

    status, kind, body = fetch(f"{base}/api/preview?project={project}&number=1")
    assert (status, kind) == (200, "image/png") and body.startswith(b"\x89PNG")
    assert fetch(f"{base}/api/preview?project={project}&number=2")[0] == 400
    assert fetch(f"{base}/api/preview?project={project}&number=removed")[0] == 400


def test_static_assets_include_the_bundled_font_and_theme_script(server):
    base, _, _ = server
    status, kind, body = fetch(f"{base}/assets/inter-latin-wght.woff2")
    assert (status, kind) == (200, "font/woff2") and body[:4] == b"wOF2"
    status, kind, _ = fetch(f"{base}/theme.js")
    assert status == 200 and "javascript" in kind
    assert fetch(f"{base}/assets/Inter-OFL.txt")[0] == 404
    assert fetch(f"{base}/server.py")[0] == 404
