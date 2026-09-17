"""Import → precise configuration → real worker → EVC provenance regressions."""

import json
import sys
import time
from pathlib import Path

import pytest
from ace_workbench.workflow.detectors import DetectorRegistry
from ace_workbench.workflow.models import Candidate
from ace_workbench.workflow.pipelines import CNMFEPipeline, QuestionEngine
from ace_workbench.workflow.runners.tables import TraceRunner


def upload(client, files):
    response = client.post(
        "/api/workflow/imports", json={"files": [{"path": name, "size": len(data)} for name, data in files.items()]}
    )
    assert response.status_code == 200, response.text
    key = response.json()["id"]
    for index, data in enumerate(files.values()):
        if data:
            response = client.put(
                f"/api/workflow/imports/{key}/files/{index}?offset=0",
                content=data,
                headers={"content-type": "application/octet-stream"},
            )
            assert response.status_code == 200, response.text
    response = client.post(f"/api/workflow/imports/{key}/inspect")
    assert response.status_code == 200, response.text
    return key, response.json()


def configured(service, name="Imported experiment"):
    client, _, registry, _ = service
    key, info = upload(client, {"session/traces.csv": b"time_s,signal\n0,1\n0.5,3\n1,5\n"})
    candidate = next(c for c in info["candidates"] if c["format"] == "trace-csv")
    body = {
        "candidate": candidate["id"],
        "pipeline": "trace-summary",
        "answers": {"signal_unit": "uV"},
        "destination": "new",
        "name": name,
    }
    response = client.post(f"/api/workflow/imports/{key}/setup", json=body)
    assert response.status_code == 200, response.text
    return key, response.json(), registry


def preflight(client, setup):
    response = client.post(
        "/api/workflow/preflight", json={"workspace": setup["workspace"]["id"], "configuration": setup["configuration"]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def wait_job(client, key):
    for _ in range(100):
        response = client.get(f"/api/workflow/runs/{key}")
        assert response.status_code == 200, response.text
        job = response.json()
        if job["state"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(0.05)
    pytest.fail("Worker did not finish in time")


@pytest.mark.parametrize("path", ["../escape", "/absolute", "a\\b", "a/../b", ".evc/config", "a//b", "CON.txt"])
def test_import_rejects_unsafe_paths(service, path):
    client, *_ = service
    response = client.post("/api/workflow/imports", json={"files": [{"path": path, "size": 1}]})
    assert response.status_code == 400


def test_upload_offsets_duplicates_and_incomplete_files(service):
    client, *_ = service
    response = client.post("/api/workflow/imports", json={"files": [{"path": "signal.raw", "size": 4}]})
    key = response.json()["id"]
    url = f"/api/workflow/imports/{key}/files/0"
    assert client.put(url + "?offset=0", content=b"ab").status_code == 200
    assert client.put(url + "?offset=0", content=b"ab").status_code == 200
    assert client.put(url + "?offset=0", content=b"xx").status_code == 409
    assert client.put(url + "?offset=3", content=b"d").status_code == 409
    assert client.post(f"/api/workflow/imports/{key}/inspect").status_code == 409
    assert client.put(url + "?offset=2", content=b"cd").status_code == 200
    info = client.post(f"/api/workflow/imports/{key}/inspect").json()
    assert info["candidates"][0]["format"] == "unknown"
    assert len(info["files"][0]["sha256"]) == 64
    assert client.put(url + "?offset=0", content=b"ab").status_code == 409


def test_duplicate_paths_and_prefixes_rejected(service):
    client, *_ = service
    for names in [("a.csv", "A.csv"), ("a", "a/b")]:
        assert (
            client.post("/api/workflow/imports", json={"files": [{"path": n, "size": 1} for n in names]}).status_code
            == 400
        )


def test_conditional_questions_do_not_invent_scientific_values():
    known = Candidate("id", "ucla-miniscope", "UCLA", ".", [], metadata={"frame_rate": 20, "calcium_evidence": True})
    pipeline = CNMFEPipeline()
    assert "frame_rate" not in {q.key for q in pipeline.questions(known)}
    assert next(q for q in pipeline.questions(known) if q.key == "decay_time").default is None
    with pytest.raises(ValueError, match="Indicator decay"):
        QuestionEngine().validate(pipeline, known, {})
    with pytest.raises(ValueError, match="finite number"):
        QuestionEngine().validate(pipeline, known, {"decay_time": True})
    known.metadata = {}
    assert "frame_rate" in {q.key for q in pipeline.questions(known)}


def test_multiple_recordings_are_distinct_and_raw_is_not_rhs(tmp_path):
    files = []
    for folder in ("session-a", "session-b"):
        path = tmp_path / folder
        path.mkdir()
        for name, data in [
            ("metaData.json", b'{"frameRate":20}'),
            ("timeStamps.csv", b"frame,time\n0,0\n1,50\n"),
            ("0.avi", b"not-yet-validated"),
        ]:
            (path / name).write_bytes(data)
            files.append({"path": folder + "/" + name})
    (tmp_path / "other.raw").write_bytes(b"arbitrary")
    files.append({"path": "other.raw"})
    candidates = DetectorRegistry().inspect(tmp_path, files)
    assert len(candidates) == 2
    assert {c.directory for c in candidates} == {"session-a", "session-b"}
    assert all(c.format == "ucla-miniscope" for c in candidates)


def test_trace_workflow_runs_and_preserves_inputs_in_evc(service):
    client, *_ = service
    key, setup, registry = configured(service)
    workspace = setup["workspace"]["id"]
    root = registry.root(workspace)
    original = (root / f"artifacts/recordings/{key}/session/traces.csv").read_bytes()
    assert not any(path.startswith("artifacts/") for path in registry.evc(workspace).show("HEAD").files)
    plan = preflight(client, setup)
    assert plan["report"]["ok"], plan
    assert plan["report"]["rows"] == 3
    response = client.post("/api/workflow/runs", json={"plan": plan["id"]})
    assert response.status_code == 200, response.text
    job = wait_job(client, plan["id"])
    assert job["state"] == "succeeded", job
    assert job["pre_revision"] and job["post_revision"]
    result = json.loads((Path(job["output"]) / "trace-summary.json").read_text())
    assert result["channels"][0]["mean"] == 3
    assert result["channels"][0]["sample_sd"] == 2
    assert result["duration_seconds"] == 1
    assert (root / f"artifacts/recordings/{key}/session/traces.csv").read_bytes() == original
    verify = client.post(f"/api/workspaces/{workspace}/results/{plan['id']}/verify")
    assert verify.json()["clean"]
    assert client.post("/api/workflow/runs", json={"plan": plan["id"]}).status_code == 409
    assert client.delete(f"/api/workflow/imports/{key}").status_code == 409


def test_changed_input_prevents_a_successful_run(service):
    client, *_ = service
    key, setup, registry = configured(service)
    plan = preflight(client, setup)
    path = registry.root(setup["workspace"]["id"]) / f"artifacts/recordings/{key}/session/traces.csv"
    path.write_bytes(path.read_bytes().replace(b"0.5,3", b"0.5,9"))
    assert client.post("/api/workflow/runs", json={"plan": plan["id"]}).status_code == 200
    job = wait_job(client, plan["id"])
    assert job["state"] == "failed"
    assert "Input changed after import" in job["log"]
    assert not (registry.root(setup["workspace"]["id"]) / f"results/{plan['id']}/manifest.json").exists()


def test_changed_configuration_invalidates_preflight(service):
    client, *_ = service
    _, setup, registry = configured(service)
    plan = preflight(client, setup)
    path = registry.root(setup["workspace"]["id"]) / setup["configuration"]
    path.write_text(path.read_text() + "\n")
    assert client.post("/api/workflow/runs", json={"plan": plan["id"]}).status_code == 409


def test_existing_experiment_does_not_replace_parameters(service):
    client, _, registry, workspace = service
    before = (registry.root(workspace) / "parameters/experiment.json").read_bytes()
    key, info = upload(client, {"arbitrary.raw": b"abc"})
    body = {"candidate": "unrecognized", "pipeline": "inventory", "answers": {}, "destination": workspace}
    response = client.post(f"/api/workflow/imports/{key}/setup", json=body)
    assert response.status_code == 200, response.text
    assert (registry.root(workspace) / "parameters/experiment.json").read_bytes() == before


@pytest.mark.parametrize("rows", ["0,1\n0,2\n1,3\n", "0,1\n1,NaN\n2,3\n", "0,1\n1,\n2,3\n", "0,1\n1,2,3\n2,3\n"])
def test_trace_preflight_rejects_data_loss_cases(tmp_path, rows):
    (tmp_path / "t.csv").write_text("time_s,x\n" + rows)
    config = {
        "candidate": {"metadata": {"table": "t.csv", "columns": ["time_s", "x"]}},
        "effective": {"time_column": "time_s", "time_unit": "seconds", "signal_unit": "uV"},
    }
    with pytest.raises(ValueError):
        TraceRunner().check(tmp_path, config)


def test_cancel_stops_worker_and_blocks_mutations(service, monkeypatch):
    client, *_ = service
    _, setup, _ = configured(service)
    plan = preflight(client, setup)
    manager = client.app.state.jobs
    monkeypatch.setattr(manager, "command", lambda *args: [sys.executable, "-c", "import time; time.sleep(60)"])
    assert client.post("/api/workflow/runs", json={"plan": plan["id"]}).status_code == 200
    assert client.post("/api/workflow/runs", json={"plan": plan["id"]}).status_code == 409
    workspace = setup["workspace"]["id"]
    doc = client.get(f"/api/workspaces/{workspace}/document", params={"path": setup["configuration"]}).json()
    assert (
        client.put(
            f"/api/workspaces/{workspace}/document",
            json={"path": doc["path"], "text": doc["text"], "etag": doc["etag"]},
        ).status_code
        == 400
    )
    assert client.post(f"/api/workflow/runs/{plan['id']}/cancel").status_code == 200
    assert wait_job(client, plan["id"])["state"] == "cancelled"
    assert workspace not in manager.registry.active


def test_failed_copy_rolls_back_new_experiment_and_keeps_staging(service, monkeypatch):
    import ace_workbench.workflow.service as module

    client, _, registry, _ = service
    key, info = upload(client, {"data.bin": b"original"})

    def broken_copy(source, target):
        target.mkdir()
        (target / "partial").write_bytes(b"incomplete")
        raise OSError("simulated disk failure")

    monkeypatch.setattr(module.shutil, "copytree", broken_copy)
    response = client.post(
        f"/api/workflow/imports/{key}/setup",
        json={
            "candidate": info["candidates"][0]["id"],
            "pipeline": "inventory",
            "answers": {},
            "destination": "new",
            "name": "Failed copy",
        },
    )
    assert response.status_code == 400
    assert not (registry.project / "Failed copy").exists()
    assert client.get(f"/api/workflow/imports/{key}").json()["state"] == "inspected"
    assert (client.app.state.workflow.imports.directory(key) / "files/data.bin").read_bytes() == b"original"


def test_source_mutation_during_setup_cannot_be_recorded(service):
    client, _, registry, _ = service
    key, info = upload(client, {"data.bin": b"original"})
    (client.app.state.workflow.imports.directory(key) / "files/data.bin").write_bytes(b"modified")
    response = client.post(
        f"/api/workflow/imports/{key}/setup",
        json={
            "candidate": info["candidates"][0]["id"],
            "pipeline": "inventory",
            "answers": {},
            "destination": "new",
            "name": "Changed source",
        },
    )
    assert response.status_code == 400
    assert not (registry.project / "Changed source").exists()


def test_restart_marks_unfinished_run_and_does_not_report_success(service):
    from ace_workbench.workflow.common import atomic_json
    from ace_workbench.workflow.jobs import JobManager

    client, _, registry, workspace = service
    manager = client.app.state.jobs
    key = "f" * 32
    atomic_json(manager.path(key), {"id": key, "workspace": workspace, "state": "running", "created": 0})
    manager.shutdown()
    replacement = JobManager(client.app.state.workflow)
    try:
        assert replacement.read(key)["state"] == "interrupted"
        assert replacement.current is None
    finally:
        replacement.shutdown()


def test_second_project_session_cannot_reclassify_live_runs(service):
    from ace_workbench.workflow.jobs import JobManager

    client, *_ = service
    with pytest.raises(ValueError, match="already open"):
        JobManager(client.app.state.workflow)


def test_unknown_camera_needs_content_confirmation_and_behavior_is_blocked(tmp_path):
    (tmp_path / "metaData.json").write_text('{"frameRate":20,"deviceType":"WebCam"}')
    (tmp_path / "timeStamps.csv").write_text("Frame Number,Time Stamp (ms)\n0,0\n1,50\n")
    (tmp_path / "0.avi").write_bytes(b"video")
    candidate = DetectorRegistry().inspect(tmp_path, [{"path": p.name} for p in tmp_path.iterdir()])[0]
    assert any("behavior camera" in error for error in candidate.blockers)
    candidate.metadata = {"frame_rate": 20}
    assert "recording_content" in {q.key for q in CNMFEPipeline().questions(candidate)}
