"""Loaders page routes, over HTTP against a real ProjectServer."""

import hashlib
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from aceneurotools.gui import features as enabled_features
from aceneurotools.gui import loaders
from aceneurotools.gui.routes import load_features
from aceneurotools.gui.server import ProjectServer
from aceneurotools.shared.loader_definitions import check_definition_text, validate_definition

FIXTURES = Path(__file__).parent / "data" / "loaders"


def definition(name="my-rig", **changes):
    data = json.loads((FIXTURES / "neuralynx.json").read_text())
    data["name"] = name
    data["label"] = "My rig"
    data.update(changes)
    return json.dumps(data, indent=2) + "\n"


@pytest.fixture
def served(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "experiments.csv").write_text(
        "line number,id,ephys directory\n1,R1,recordings/nlx\n2,R2,\n3,R3,recordings/missing\n4,R4,recordings/empty\n"
    )
    (root / "analysis_parameters.csv").write_text("line number,crop\n1,False\n2,False\n3,False\n4,False\n")
    nlx = root / "recordings" / "nlx"
    nlx.mkdir(parents=True)
    (nlx / "Events.nev").write_bytes(b"")
    (nlx / "CSC1.ncs").write_bytes(b"")
    (root / "recordings" / "empty").mkdir()
    server = ProjectServer(("127.0.0.1", 0), str(root), features=load_features(["aceneurotools.gui.loaders"]))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    project = next(iter(server.projects.values()))
    yield base, server, project
    server.shutdown()
    server.server_close()
    worker.join(timeout=2)


def call(served, route, payload=None, **query):
    base, server, _ = served
    headers = {"Authorization": "Bearer " + server.token}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    url = base + route + (f"?{urlencode(query)}" if query else "")
    req = Request(url, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
    try:
        response = urlopen(req, timeout=20)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.loads(response.read())


def save(served, name, text, digest=None):
    return call(served, "/api/loaders/save", {"project": served[2].id, "name": name, "text": text, "digest": digest})


def folder(served):
    return Path(served[2].path) / "loaders"


def test_feature_is_enabled_and_templates_are_valid():
    assert "aceneurotools.gui.loaders" in enabled_features.ENABLED
    for template_id, *_ in loaders.TEMPLATES:
        data, problems = check_definition_text((loaders.TEMPLATES_DIR / f"{template_id}.json").read_text())
        assert problems == [], template_id
        assert data["modality"] == "ephys"
    backends = {
        json.loads((loaders.TEMPLATES_DIR / f"{template_id}.json").read_text())["reader"]["backend"]
        for template_id, *_ in loaders.TEMPLATES
    }
    assert backends == {"neo", "raw_binary"}


def test_routes_require_the_launch_token(served):
    base, _, project = served
    with pytest.raises(HTTPError) as error:
        urlopen(f"{base}/api/loaders?project={project.id}", timeout=5)
    assert error.value.code == 401


def test_list_shows_builtins_and_project_definitions(served):
    folder(served).mkdir()
    (folder(served) / "my-rig.json").write_text(definition())
    (folder(served) / "broken.json").write_text("{not json")
    (folder(served) / "neuralynx.json").write_text((FIXTURES / "neuralynx.json").read_text())
    (folder(served) / "Bad Name.json").write_text(definition())
    status, result = call(served, "/api/loaders", project=served[2].id)
    assert status == 200
    names = [item["name"] for item in result["builtins"]]
    assert names == ["NeuralynxDataManager", "RHS2116DataManager"]
    assert "neuralynx" in result["builtins"][0]["reserved"]
    entries = {item["name"]: item for item in result["definitions"]}
    assert entries["my-rig"]["valid"] and entries["my-rig"]["backend"] == "neo" and entries["my-rig"]["label"] == "My rig"
    content = (folder(served) / "my-rig.json").read_bytes()
    assert entries["my-rig"]["digest"] == hashlib.sha256(content).hexdigest()
    assert entries["my-rig"]["file"] == "loaders/my-rig.json"
    assert not entries["broken"]["valid"] and "invalid JSON" in entries["broken"]["problems"][0]["message"]
    assert not entries["neuralynx"]["valid"]
    assert any("built-in" in item["message"] for item in entries["neuralynx"]["problems"])
    assert not entries["Bad Name"]["editable"]
    assert result["preview"]["available"] is False and "ADR 0008" in result["preview"]["note"]
    # No absolute paths leak into the listing.
    assert str(served[2].path) not in json.dumps(result["definitions"])


def test_list_without_loaders_folder(served):
    status, result = call(served, "/api/loaders", project=served[2].id)
    assert status == 200 and result["definitions"] == [] and result["folder_exists"] is False


def test_get_definition_and_schema(served):
    folder(served).mkdir()
    text = definition()
    (folder(served) / "my-rig.json").write_text(text)
    status, result = call(served, "/api/loaders/definition", project=served[2].id, name="my-rig")
    assert status == 200
    assert result["text"] == text and result["problems"] == []
    assert result["digest"] == hashlib.sha256(text.encode()).hexdigest()
    status, result = call(served, "/api/loaders/definition", project=served[2].id, name="absent")
    assert status == 400
    status, result = call(served, "/api/loaders/schema")
    assert status == 200
    assert result["schema"]["properties"]["schema"]["const"] == "ace-loader/1"
    assert "NeuralynxIO" in result["choices"]["neo_ios"]
    assert "PickleIO" not in result["choices"]["neo_ios"]
    assert {item["id"] for item in result["templates"]} == {"neo-reader", "raw-binary"}


def test_validate_reports_problems_for_drafts(served):
    project = served[2].id
    status, result = call(served, "/api/loaders/validate", {"project": project, "text": definition()})
    assert status == 200 and result == {"valid": True, "problems": []}
    bad = json.loads(definition())
    bad["reader"]["io"] = "NeuralynxIOO"
    status, result = call(served, "/api/loaders/validate", {"project": project, "text": json.dumps(bad)})
    assert not result["valid"]
    assert result["problems"] == [
        {"path": item.path, "message": item.message} for item in validate_definition(bad)
    ]
    status, result = call(served, "/api/loaders/validate", {"project": project, "text": '{"a": 1, "a": 2}'})
    assert "duplicate key" in result["problems"][0]["message"]
    status, result = call(served, "/api/loaders/validate", {"project": project, "text": definition("rhs2116")})
    assert any("built-in" in item["message"] for item in result["problems"])
    # Editing a saved loader: the name must stay the file name.
    status, result = call(
        served, "/api/loaders/validate", {"project": project, "text": definition("other"), "name": "my-rig"}
    )
    assert any("file name" in item["message"] for item in result["problems"])
    # A new loader may not reuse an existing file's name.
    save(served, "my-rig", definition())
    status, result = call(served, "/api/loaders/validate", {"project": project, "text": definition()})
    assert any("already has" in item["message"] for item in result["problems"])
    status, result = call(served, "/api/loaders/validate", {"project": project, "text": "[" * 100000})
    assert status == 200 and not result["valid"]


def test_save_new_update_conflict_and_backup(served):
    text = definition()
    status, result = save(served, "my-rig", text)
    assert status == 200 and result["created"] and result["backup"] is None
    path = folder(served) / "my-rig.json"
    assert path.read_text() == text
    assert result["digest"] == hashlib.sha256(text.encode()).hexdigest()
    assert not list(folder(served).glob(".ace-loader-*"))

    # A second "new" save with the same name is a conflict.
    status, error = save(served, "my-rig", text)
    assert status == 409 and error["reload"]

    first_digest = result["digest"]
    updated = definition(label="Renamed rig")
    status, result = save(served, "my-rig", updated, first_digest)
    assert status == 200 and not result["created"]
    backup = Path(result["backup"])
    assert backup.parent == Path(served[2].path) / ".ace-gui-backups"
    assert backup.read_text() == text
    assert path.read_text() == updated

    # Saving from the stale first copy is refused and changes nothing.
    status, error = save(served, "my-rig", definition(label="Stale"), first_digest)
    assert status == 409 and error["reload"] and "changed" in error["error"]
    assert path.read_text() == updated

    # Saving identical text writes nothing and keeps no backup.
    backups = sorted((Path(served[2].path) / ".ace-gui-backups").iterdir())
    status, same = save(served, "my-rig", updated, result["digest"])
    assert status == 200 and same["backup"] is None and same["digest"] == result["digest"]
    assert sorted((Path(served[2].path) / ".ace-gui-backups").iterdir()) == backups

    # Text without a trailing newline gets one.
    status, result = save(served, "my-rig", updated.rstrip("\n").replace("Renamed", "Third"), result["digest"])
    assert status == 200 and path.read_text().endswith("}\n")


def test_save_refuses_invalid_reserved_and_bad_names(served):
    bad = json.loads(definition())
    del bad["sync"]
    status, error = save(served, "my-rig", json.dumps(bad))
    assert status == 400 and "Fix this loader" in error["error"] and "sync" in error["error"]
    status, error = save(served, "neuralynx", definition("neuralynx"))
    assert status == 400 and "built-in" in error["error"]
    status, error = save(served, "my-rig", definition("other-name"))
    assert status == 400 and "file name" in error["error"]
    for name in ("../escape", "My Rig", "a/b", "", None, 5, "x" * 65, "loaders/../x"):
        status, error = save(served, name, definition("x"))
        assert status == 400 and "Loader names" in error["error"], name
    assert not folder(served).exists() or not list(folder(served).iterdir())
    assert not (Path(served[2].path).parent / "escape.json").exists()


def test_save_refuses_linked_files(served, tmp_path):
    folder(served).mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text(definition())
    (folder(served) / "my-rig.json").symlink_to(outside)
    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    status, error = save(served, "my-rig", definition(label="Changed"), digest)
    assert status == 400 and "link" in error["error"]
    assert outside.read_text() == definition()


def test_delete_checks_digest_and_keeps_backup(served):
    text = definition()
    _, result = save(served, "my-rig", text)
    status, error = call(
        served, "/api/loaders/delete", {"project": served[2].id, "name": "my-rig", "digest": "0" * 64}
    )
    assert status == 409 and (folder(served) / "my-rig.json").exists()
    status, error = call(served, "/api/loaders/delete", {"project": served[2].id, "name": "my-rig", "digest": None})
    assert status == 400
    status, result = call(
        served, "/api/loaders/delete", {"project": served[2].id, "name": "my-rig", "digest": result["digest"]}
    )
    assert status == 200
    assert not (folder(served) / "my-rig.json").exists()
    assert Path(result["backup"]).read_text() == text
    status, error = call(
        served, "/api/loaders/delete", {"project": served[2].id, "name": "my-rig", "digest": "0" * 64}
    )
    assert status == 409


def test_detect_matches_builtins_and_definitions(served):
    save(served, "my-rig", definition())
    save(served, "dat-rig", definition("dat-rig", detect={"all_of": ["*.dat"]}))
    status, result = call(served, "/api/loaders/detect", {"project": served[2].id, "number": "1"})
    assert status == 200 and result["status"] == "ok"
    assert result["folder"] == str((Path(served[2].path) / "recordings" / "nlx").resolve())
    builtins = {item["name"]: item["matches"] for item in result["builtins"]}
    assert builtins == {"NeuralynxDataManager": True, "RHS2116DataManager": False}
    assert result["builtin_used"] == "NeuralynxDataManager"
    own = {item["name"]: item for item in result["definitions"]}
    assert own["my-rig"]["matches"] and not own["dat-rig"]["matches"]
    assert own["my-rig"]["patterns"] == [{"pattern": "*.nev", "rule": ["any_of"], "count": 1, "examples": ["Events.nev"]}]
    assert result["draft"] is None

    draft = definition("draft-rig", detect={"all_of": ["*.ncs"]})
    status, result = call(served, "/api/loaders/detect", {"project": served[2].id, "number": "1", "text": draft})
    assert result["draft"]["valid"] and result["draft"]["matches"]
    status, result = call(served, "/api/loaders/detect", {"project": served[2].id, "number": "1", "text": "{}"})
    assert result["draft"]["valid"] is False


def test_detect_no_match_and_missing_folders(served):
    status, result = call(served, "/api/loaders/detect", {"project": served[2].id, "number": "4"})
    assert status == 200 and result["status"] == "ok"
    assert not any(item["matches"] for item in result["builtins"]) and result["builtin_used"] is None
    status, result = call(served, "/api/loaders/detect", {"project": served[2].id, "number": "2"})
    assert result["status"] == "no-directory" and "no ephys directory" in result["message"]
    status, result = call(served, "/api/loaders/detect", {"project": served[2].id, "number": "3"})
    assert result["status"] == "missing" and "not on this computer" in result["message"]
    status, result = call(served, "/api/loaders/detect", {"project": served[2].id, "number": "99"})
    assert status == 400


def test_no_route_accepts_a_path(served, tmp_path):
    """Paths in requests are ignored or refused; nothing outside loaders/ is read or written."""
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "Events.nev").write_bytes(b"")
    project = served[2].id
    for extra in ({"path": str(outside)}, {"directory": str(outside)}, {"data_path": str(outside)}):
        status, result = call(served, "/api/loaders/detect", {"project": project, "number": "4", **extra})
        assert status == 200 and result["builtin_used"] is None
        status, result = call(served, "/api/loaders", project=project, **extra)
        assert status == 200 and result["definitions"] == []
    for name in (str(outside / "x"), "../../elsewhere/x", "..", "x.json"):
        status, _ = call(served, "/api/loaders/definition", project=project, name=name)
        assert status == 400
        status, _ = call(served, "/api/loaders/delete", {"project": project, "name": name, "digest": "0" * 64})
        assert status == 400
    assert sorted(item.name for item in outside.iterdir()) == ["Events.nev"]


def test_deeply_nested_file_is_reported_not_dropped(served):
    folder(served).mkdir()
    (folder(served) / "deep.json").write_text("[" * 100000)
    status, result = call(served, "/api/loaders", project=served[2].id)
    # load_project_definitions currently raises RecursionError here; the page reports
    # it plainly. If that is fixed upstream, the file is listed as invalid instead.
    if status == 400:
        assert "nested too deeply" in result["error"]
    else:
        assert status == 200 and not result["definitions"][0]["valid"]
    status, result = call(served, "/api/loaders/definition", project=served[2].id, name="deep")
    assert status == 200 and "invalid JSON" in result["problems"][0]["message"]
