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
    assert headers["Content-Disposition"] == "attachment; filename=\"plot_1_.png\"; filename*=UTF-8''plot%221%22.png"
    assert headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize(
    "fields",
    [
        {"download_name": "a.txt\r\nX-Injected: yes"},
        {"download_name": "tab\tname.png"},
        {"download_name": "  "},
        {"content_type": "text/plain\r\nX-Injected: yes"},
        {"content_type": "text/plain; café"},
    ],
)
def test_file_responses_reject_header_injection_before_sending(fields):
    with pytest.raises(ValueError):
        FileResponse(**{"content_type": "text/plain", "body": b"x", **fields})


def test_unicode_download_names_use_an_ascii_fallback_and_the_exact_name():
    response = FileResponse("image/png", body=b"x", download_name="café – plot.png")
    assert response.disposition() == (
        "attachment; filename=\"caf_ _ plot.png\"; filename*=UTF-8''caf%C3%A9%20%E2%80%93%20plot.png"
    )
    response.disposition().encode("latin-1")  # What http.server needs to send it.


def test_feature_posts_keep_origin_type_and_size_checks(served):
    base, server, project = served
    route = "/api/probe/experiment"
    payload = {"project": project.id, "number": "1"}

    def raw(headers, data):
        req = Request(base + route, data=data, headers={"Authorization": "Bearer " + server.token, **headers})
        try:
            return urlopen(req, timeout=5).status
        except HTTPError as error:
            return error.code

    body = json.dumps(payload).encode()
    assert raw({"Content-Type": "application/json", "Origin": "http://evil.example"}, body) == 403
    assert raw({"Content-Type": "text/plain"}, body) == 403
    large = json.dumps({**payload, "pad": "x" * 300000}).encode()
    assert raw({"Content-Type": "application/json"}, large) == 400
    assert raw({"Content-Type": "application/json"}, body) == 200


def test_feature_routes_cannot_shadow_built_in_routes():
    clash = Feature(name="clash", routes=(Route("POST", "/api/run/start", _none),))
    with pytest.raises(ValueError, match="replace built-in routes"):
        ProjectServer(("127.0.0.1", 0), None, features=[clash])
    clash = Feature(name="clash", routes=(Route("GET", "/api/run/file", _none),))
    with pytest.raises(ValueError, match="replace built-in routes"):
        ProjectServer(("127.0.0.1", 0), None, features=[clash])


def test_feature_services_are_built_after_the_server_state_they_use(tmp_path):
    (tmp_path / "experiments.csv").write_text("line number,id\n1,R1\n")
    seen = {}

    def service(server):
        seen.update(lock=server.lock, projects=len(server.projects), runs=server.runs)
        return "ready"

    server = ProjectServer(("127.0.0.1", 0), str(tmp_path), features=[Feature(name="queue", service=service)])
    try:
        assert server.services == {"queue": "ready"}
        assert seen["projects"] == 1 and seen["lock"] is server.lock and seen["runs"] is server.runs
    finally:
        server.server_close()


def test_context_reads_body_for_post_and_query_for_get():
    get = Context(None, "GET", "/api/x", {"a": "1"}, {"a": "body"})
    post = Context(None, "POST", "/api/x", {"a": "query"}, {"a": 2})
    assert get.value("a") == "1" and post.value("a") == 2 and post.value("missing", "d") == "d"


def test_declaration_errors_and_helpers():
    assert FileResponse("text/plain", body=b"x").disposition() is None
    with pytest.raises(ValueError, match="Unsupported method"):
        Route("PUT", "/api/x", _none)
    one = Feature(name="one", scripts=("shared.js",))
    two = Feature(name="two", scripts=("shared.js",))
    with pytest.raises(ValueError, match="Browser file registered twice"):
        Registry([one, two])
    with pytest.raises(TypeError, match="does not define FEATURE"):
        load_features(["aceneurotools.gui.fields"])

    class FakeServer:
        projects = {}

    class FakeProject:
        id = "p1"

    context = Context(FakeServer(), "POST", "/api/x", {}, {})
    replacement = FakeProject()
    context.replace_project(replacement)
    assert FakeServer.projects == {"p1": replacement} and context.project is replacement


def test_file_responses_stream_files_from_disk(tmp_path):
    payload = b"line one\nline two\n" * 1000
    source = tmp_path / "result.csv"
    source.write_bytes(payload)
    feature = Feature(
        name="files",
        routes=(Route("GET", "/api/files/result", lambda context: FileResponse("text/csv", path=source), scope="none"),),
    )
    server = ProjectServer(("127.0.0.1", 0), None, features=[feature])
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        status, (headers, body) = call(base, server, "/api/files/result", raw=True)
        assert status == 200 and body == payload
        assert headers["Content-Length"] == str(len(payload)) and headers["Content-Type"] == "text/csv"
        source.unlink()
        status, error = call(base, server, "/api/files/result")
        assert status == 400 and "error" in error, "a missing file is an ordinary error, sent before any headers"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_locked_routes_recheck_the_experiment_in_the_latest_project(served):
    """If the project is reloaded without the experiment before the lock is taken, the handler must not run."""
    base, server, project = served
    from aceneurotools.gui.csv_projects import Project

    (project.path / "experiments.csv").write_text("line number,id\n2,R2\n")
    (project.path / "analysis_parameters.csv").write_text("line number,crop\n2,False\n")
    reloaded = Project.open(project.path)
    assert "1" not in reloaded.experiments

    class ReloadedDuringRequest(dict):
        """Scope resolution (get) still sees the old copy; the locked re-fetch ([]) sees the reload."""

        def get(self, key, default=None):
            return project if key == project.id else default

        def __getitem__(self, key):
            return reloaded

    server.projects = ReloadedDuringRequest({project.id: project})
    CALLS.clear()
    status, error = call(base, server, "/api/probe/experiment", {"project": project.id, "number": "1"})
    assert status == 400 and "Experiment 1 was not found" in error["error"]
    assert CALLS == [], "the handler did not run"
