"""Verify real local HTTP loading, failure preservation, and snapshot reloads."""

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from gui.server import ProjectServer


@pytest.fixture
def viewer(tmp_path):
    (tmp_path / "experiments.csv").write_text("line number,id\n1,R1\n")
    (tmp_path / "analysis_parameters.csv").write_text("line number,crop\n1,False\n")
    server = ProjectServer(("127.0.0.1", 0), str(tmp_path))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", tmp_path
    server.shutdown()
    server.server_close()
    worker.join(timeout=2)


def request(base, route, payload=None, headers=None):
    options = {"Content-Type": "application/json"} if payload is not None else {}
    options.update(headers or {})
    req = Request(base + route, data=json.dumps(payload).encode() if payload is not None else None, headers=options)
    try:
        response = urlopen(req, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.loads(response.read())


def test_load_and_inspect_actual_csvs(viewer):
    base, folder = viewer
    status, result = request(base, "/api/projects")
    assert status == 200
    project = result["projects"][0]
    assert project["path"] == str(folder)
    status, detail = request(base, f"/api/experiment?project={project['id']}&number=1")
    assert status == 200
    assert detail["metadata"]["id"] == "R1"
    assert detail["parameters"]["crop"] == "False"
    status, listing = request(base, f"/api/folders?path={folder}")
    assert status == 200
    assert listing["has_experiments"] and listing["has_parameters"]


def test_failed_open_keeps_current_project(viewer):
    base, folder = viewer
    invalid = folder / "invalid"
    invalid.mkdir()
    (invalid / "experiments.csv").write_text("line number,id\n1,R1,extra\n")
    status, error = request(base, "/api/projects/open", {"path": str(invalid)})
    assert status == 400
    assert "expected 2 columns" in error["error"]
    assert len(request(base, "/api/projects")[1]["projects"]) == 1


def test_changed_snapshot_requires_reload_over_http(viewer):
    base, folder = viewer
    project = request(base, "/api/projects")[1]["projects"][0]
    (folder / "experiments.csv").write_text("line number,id\n1,Rupdated\n")
    route = f"/api/experiment?project={project['id']}&number=1"
    status, error = request(base, route)
    assert status == 409 and error["reload"] is True
    assert request(base, "/api/projects/open", {"path": str(folder)})[0] == 200
    assert request(base, route)[1]["metadata"]["id"] == "Rupdated"


def test_foreign_origin_and_host_are_rejected(viewer):
    base, folder = viewer
    assert request(base, "/api/projects", headers={"Host": "foreign.invalid"})[0] == 403
    assert request(base, "/api/projects/open", {"path": str(folder)}, {"Origin": "https://foreign.invalid"})[0] == 403


def test_save_over_http_updates_csv_and_refreshes_project(viewer):
    base, folder = viewer
    project = request(base, "/api/projects")[1]["projects"][0]
    route = f"/api/experiment?project={project['id']}&number=1"
    detail = request(base, route)[1]
    body = {
        "project": project["id"],
        "number": "1",
        "section": "metadata",
        "changes": {"id": "Rchanged"},
        "versions": detail["versions"],
    }
    status, saved = request(base, "/api/experiment/save", body)
    assert status == 200
    assert saved["experiment"]["metadata"]["id"] == "Rchanged"
    assert saved["project"]["experiments"][0]["subject"] == "Rchanged"
    assert request(base, route)[1]["metadata"]["id"] == "Rchanged"
    assert saved["backup"]
    body["changes"] = {"id": "stale"}
    status, error = request(base, "/api/experiment/save", body)
    assert status == 409 and error["reload"]
    assert request(base, route)[1]["metadata"]["id"] == "Rchanged"
