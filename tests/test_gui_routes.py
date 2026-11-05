"""Feature routes keep the server's protections and resolve projects consistently."""

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from aceneurotools.gui import features as enabled_features
from aceneurotools.gui.csv_projects import ProjectChangedError, ProjectError
from aceneurotools.gui.routes import Context, Feature, FileResponse, Registry, Route, load_features
from aceneurotools.gui.server import ProjectServer

CALLS = []


def _none(context):
    return {"scope": "none", "query": context.query}


def _project(context):
    return {"project": context.project.id, "number": context.number}


def _experiment(context):
    CALLS.append(context.server.lock.locked())
    return {"number": context.number, "value": context.value("value")}


def _image(context):
    return FileResponse("image/png", body=b"\x89PNG fake", download_name='plot"1".png')


def _changed(context):
    raise ProjectChangedError("experiments.csv changed since it was opened.")


def _invalid(context):
    raise ProjectError("Choose a valid thing.")


TEST_FEATURE = Feature(
    name="probe",
    routes=(
        Route("GET", "/api/probe/none", _none, scope="none"),
        Route("GET", "/api/probe/project", _project),
        Route("POST", "/api/probe/experiment", _experiment, scope="experiment", locked=True),
        Route("GET", "/api/probe/image", _image, scope="none"),
        Route("POST", "/api/probe/changed", _changed),
        Route("POST", "/api/probe/invalid", _invalid),
    ),
    scripts=("test-probe.js",),
)


@pytest.fixture
def served(tmp_path, monkeypatch):
    (tmp_path / "experiments.csv").write_text("line number,id\n1,R1\n")
    (tmp_path / "analysis_parameters.csv").write_text("line number,crop\n1,False\n")
    # The feature's browser file is read from the gui/ folder; serve a temporary one.
    from aceneurotools.gui import server as server_module

    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "test-probe.js").write_text('"use strict";\n')
    monkeypatch.setattr(server_module, "ASSETS", assets)
    server = ProjectServer(("127.0.0.1", 0), str(tmp_path), features=[TEST_FEATURE])
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    project = next(iter(server.projects.values()))
    yield base, server, project
    server.shutdown()
    server.server_close()
    worker.join(timeout=2)


def call(base, server, route, payload=None, token=True, raw=False):
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    if token:
        headers["Authorization"] = "Bearer " + server.token
    req = Request(base + route, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
    try:
        response = urlopen(req, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        body = response.read()
        return response.status, (response.headers, body) if raw else json.loads(body)


def test_registry_rejects_ambiguous_or_unsafe_declarations():
    with pytest.raises(ValueError, match="scope"):
        Route("GET", "/api/x", _none, scope="global")
    with pytest.raises(ValueError, match="/api/"):
        Route("GET", "/x", _none)
    with pytest.raises(ValueError, match="simple lower-case"):
        Feature(name="bad", scripts=("../app.js",))
    registry = Registry([TEST_FEATURE])
    with pytest.raises(ValueError, match="twice"):
        registry.add(TEST_FEATURE)
    with pytest.raises(ValueError, match="Route registered twice"):
        registry.add(Feature(name="other", routes=(Route("GET", "/api/probe/none", _none, scope="none"),)))
    with pytest.raises(ValueError, match="exactly one"):
        FileResponse("text/plain")


def test_enabled_features_load_and_core_files_cannot_be_replaced(tmp_path):
    names = [feature.name for feature in load_features(enabled_features.ENABLED)]
    assert "run-plan" in names
    with pytest.raises(ValueError, match="replace core files"):
        ProjectServer(("127.0.0.1", 0), None, features=[Feature(name="clash", scripts=("app.js",))])


def test_feature_manifest_lists_scripts_in_order(served):
    base, server, _ = served
    status, result = call(base, server, "/api/features")
    assert status == 200
    assert result["features"][0]["name"] == "core"
    assert {"name": "probe", "scripts": ["test-probe.js"], "styles": []} in result["features"]
    status, (headers, body) = call(base, server, "/test-probe.js", raw=True)
    assert status == 200 and body.startswith(b'"use strict"')
    assert "script-src 'self'" in headers["Content-Security-Policy"]


def test_feature_routes_require_the_launch_token(served):
    base, server, project = served
    assert call(base, server, "/api/probe/none", token=False)[0] == 401
    assert call(base, server, "/api/probe/experiment", {"project": project.id, "number": "1"}, token=False)[0] == 403
    assert call(base, server, "/api/probe/missing", {"project": project.id})[0] == 404


def test_scopes_resolve_project_and_experiment(served):
    base, server, project = served
    assert call(base, server, "/api/probe/none?a=1&a=2")[1] == {"scope": "none", "query": {"a": "1"}}
    assert call(base, server, f"/api/probe/project?project={project.id}&number=1")[1] == {
        "project": project.id,
        "number": None,
    }
    status, error = call(base, server, "/api/probe/project?project=unknown")
    assert status == 400 and error["error"] == "Open this project first."
    CALLS.clear()
    status, result = call(base, server, "/api/probe/experiment", {"project": project.id, "number": "1", "value": 3})
    assert status == 200 and result == {"number": "1", "value": 3}
    assert CALLS == [True], "locked routes run while holding the server lock"
    status, error = call(base, server, "/api/probe/experiment", {"project": project.id, "number": "9"})
    assert status == 400 and "Experiment 9 was not found" in error["error"]
    status, error = call(base, server, "/api/probe/experiment", {"project": project.id})
    assert status == 400 and error["error"] == "Choose an experiment first."


def test_errors_and_files_use_the_built_in_conventions(served):
    base, server, project = served
    status, error = call(base, server, "/api/probe/changed", {"project": project.id})
    assert status == 409 and error["reload"] is True
    status, error = call(base, server, "/api/probe/invalid", {"project": project.id})
    assert status == 400 and error == {"error": "Choose a valid thing."}
    status, (headers, body) = call(base, server, "/api/probe/image", raw=True)
    assert status == 200 and body == b"\x89PNG fake"
    assert headers["Content-Type"] == "image/png"
    assert headers["Content-Disposition"] == 'attachment; filename="plot1.png"'
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_context_reads_body_for_post_and_query_for_get():
    get = Context(None, "GET", "/api/x", {"a": "1"}, {"a": "body"})
    post = Context(None, "POST", "/api/x", {"a": "query"}, {"a": 2})
    assert get.value("a") == "1" and post.value("a") == 2 and post.value("missing", "d") == "d"
