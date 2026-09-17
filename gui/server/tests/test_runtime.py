import json

import pytest
from ace_workbench.demo import create_demo
from ace_workbench.workspaces import WorkspaceRegistry, discover


def test_demo_is_reopenable_without_replacing_researcher_edits(tmp_path):
    roots = create_demo(tmp_path / "example")
    path = roots[0] / "parameters/analysis.cnmfe.json"
    text = path.read_text() + "\n"
    path.write_text(text)
    assert create_demo(tmp_path / "example") == roots
    assert path.read_text() == text
    assert discover(tmp_path / "example") == roots
    with pytest.raises(ValueError, match="Author"):
        WorkspaceRegistry(roots, author="Name without email")


def test_demo_refuses_an_unrelated_nonempty_directory(tmp_path):
    protected = tmp_path / "research"
    protected.mkdir()
    (protected / "recording.bin").write_bytes(b"existing research")
    with pytest.raises(ValueError, match="not empty"):
        create_demo(protected)
    assert (protected / "recording.bin").read_bytes() == b"existing research"
    assert not (protected / ".ace-demo").exists()


def test_malformed_manifest_is_a_visible_run_error(service):
    client, base, registry, workspace = service
    path = registry.root(workspace) / "results/synthetic-traces/manifest.json"
    path.write_text(json.dumps({"schema": "wrong-format", "artifacts": []}))
    response = client.get(f"{base}/results")
    assert response.status_code == 200
    assert "unsupported manifest schema" in response.json()[0]["error"]


def test_oversized_parameter_file_and_unknown_workspace_are_rejected(service):
    client, base, registry, workspace = service
    (registry.root(workspace) / "parameters/large.json").write_text(" " * (2 * 1024 * 1024 + 1))
    assert client.get(f"{base}/document", params={"path": "parameters/large.json"}).status_code == 400
    assert client.get("/api/workspaces/not-registered/state").status_code == 404
