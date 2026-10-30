"""Cluster bundle import, run registration, and estimates-only event processing."""

import json
import threading
from pathlib import Path

import numpy as np
import pytest

from aceneurotools.gui.cluster_results import FORMAT, file_sha256, import_bundle
from aceneurotools.gui.csv_projects import ProjectError
from aceneurotools.gui.neurons import Neurons
from aceneurotools.gui.runs import Runs
from aceneurotools.gui.server import ProjectServer
from aceneurotools.pipelines.postprocess_estimates import postprocess_bundle
from tests.test_gui_neurons import body, wait_export
from tests.test_gui_server import TOKENS, request

pytest_plugins = ("tests.test_gui_neurons",)


def bundle_for(estimates):
    project, path, _, _ = estimates
    bundle = path.parent / "cluster-bundle"
    bundle.mkdir()
    source = bundle / "estimates.hdf5"
    source.write_bytes(path.read_bytes())
    manifest = {
        "format": FORMAT,
        "experiment": "1",
        "estimates": source.name,
        "sha256": file_sha256(source),
        "component_ids": [10, 20, 30],
        "frame_rate": 10,
        "parameters": {"run_CNMFE": True, "gSig": [3, 3]},
        "software": {"caiman": "test-version", "ace": "test-version"},
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    return project, bundle, manifest


def test_import_registers_run_and_preserves_original_component_ids(estimates):
    project, bundle, manifest = bundle_for(estimates)
    run_id = import_bundle(project, bundle)
    run = Runs().inspect(project, run_id)
    assert run["origin"] == "cluster-import" and run["state"] == "completed"
    assert run["parameters"] == manifest["parameters"]
    assert {item["name"] for item in run["files"]} >= {"manifest.json", "estimates.hdf5"}
    assert run["output_inventory"]["outputs"][0]["file"] == "estimates.hdf5"
    assert bundle.joinpath("estimates.hdf5").is_file()
    assert Runs().listing(project, "1")["runs"][0]["id"] == run_id

    service = Neurons()
    session = service.open(project, body(project, path=str(Path(run["directory"]) / "estimates.hdf5")))
    assert session["component_ids"] == [10, 20, 30]
    decision = service.decide(
        project,
        body(project, session=session["session"], revision=session["revision"], index=1, decision=True),
    )
    assert decision["decisions"] == [None, True, None]


def test_postprocess_from_imported_estimates_maps_event_ids(estimates):
    project, bundle, _ = bundle_for(estimates)
    run_id = import_bundle(project, bundle)
    output = Path(project.path) / "derived-events"
    postprocess_bundle(Path(project.path) / ".ace-runs" / run_id, output, derivative="zeroth", event_height=5)
    result = json.loads((output / "calcium-events.json").read_text())
    assert result["source_sha256"] == file_sha256(bundle / "estimates.hdf5")
    assert result["component_ids"] == [10, 20, 30]
    assert result["events_by_component_id"] == {"10": [10], "20": [300], "30": [580]}
    assert not (bundle / "derived-events").exists()
    with pytest.raises(FileExistsError):
        postprocess_bundle(bundle, output)


def test_curation_export_keeps_cluster_component_ids(estimates):
    project, bundle, _ = bundle_for(estimates)
    run_id = import_bundle(project, bundle)
    path = project.path / ".ace-runs" / run_id / "estimates.hdf5"
    service = Neurons()
    session = service.open(project, body(project, path=str(path)))
    for index, keep in enumerate([False, True, True]):
        session = service.decide(
            project,
            body(project, session=session["session"], revision=session["revision"], index=index, decision=keep),
        )
    job = service.export(
        project,
        body(project, session=session["session"], revision=session["revision"], confirmed=True, event_analysis=None),
    )
    job = wait_export(service, project, job)
    decisions = json.loads((Path(job["directory"]) / "decisions.json").read_text())
    assert decisions["neuron_ids"] == [20, 30]
    with np.load(Path(job["directory"]) / "C_curated.npz", allow_pickle=False) as values:
        np.testing.assert_array_equal(values["neuron_ids"], [20, 30])


def test_results_postprocessing_writes_a_new_child_result(estimates):
    project, bundle, _ = bundle_for(estimates)
    service = Runs()
    run_id = import_bundle(project, bundle)
    run = service.postprocess_import(
        project, {"run": run_id, "number": "1", "derivative": "zeroth", "event_height": 5}
    )
    assert any(item["name"].endswith("/calcium-events.json") for item in run["files"])
    assert (bundle / "estimates.hdf5").is_file()


def test_http_import_and_postprocessing_are_available_in_results(estimates):
    project, bundle, _ = bundle_for(estimates)
    server = ProjectServer(("127.0.0.1", 0), str(project.path))
    base = f"http://127.0.0.1:{server.server_address[1]}"
    TOKENS[base] = server.token
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        payload = {"project": project.id, "number": "1"}
        status, imported = request(base, "/api/run/import", payload | {"folder": str(bundle)})
        assert status == 200 and imported["origin"] == "cluster-import"
        status, derived = request(
            base,
            "/api/run/postprocess",
            payload | {"run": imported["id"], "derivative": "zeroth", "event_height": 5},
        )
        assert status == 200
        assert any(item["name"].endswith("/calcium-events.json") for item in derived["files"])
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_invalid_manifest_or_estimates_cannot_be_imported(estimates):
    project, bundle, manifest = bundle_for(estimates)
    manifest["sha256"] = "0" * 64
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ProjectError, match="checksum"):
        import_bundle(project, bundle)
    manifest["sha256"] = file_sha256(bundle / "estimates.hdf5")
    manifest["component_ids"] = [10, 20]
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ProjectError, match="match"):
        import_bundle(project, bundle)
    assert not (project.path / ".ace-runs").exists()
