import json

import pytest


@pytest.mark.parametrize(
    "headers,code",
    [({"x-ace-token": "bad"}, 401), ({"origin": "https://foreign.example"}, 403), ({"host": "evil.example:8765"}, 403)],
)
def test_local_session_boundary(service, headers, code):
    client, _, _, _ = service
    assert client.get("/api/session", headers=headers).status_code == code


@pytest.mark.parametrize(
    "path", ["../private.json", "/etc/passwd", "parameters/../../private.json", ".evc/HEAD", "artifacts/data.json"]
)
def test_document_path_boundary(service, path):
    client, base, _, _ = service
    assert client.get(f"{base}/document", params={"path": path}).status_code == 400


def test_symlink_is_rejected(service, tmp_path):
    client, base, registry, workspace = service
    outside = tmp_path / "outside.json"
    outside.write_text('{"private": true}')
    (registry.root(workspace) / "parameters/link.json").symlink_to(outside)
    assert client.get(f"{base}/document", params={"path": "parameters/link.json"}).status_code == 400
    assert "parameters/link.json" not in client.get(f"{base}/state").json()["documents"]


def test_result_integrity_tamper_missing_and_preview(service):
    client, base, registry, workspace = service
    endpoint = f"{base}/results/synthetic-traces"
    assert client.post(f"{endpoint}/verify").json()["clean"]
    preview = client.get(f"{endpoint}/preview", params={"path": "synthetic-traces.csv"}).json()
    assert len(preview["numeric"]) == 400
    artifact = registry.root(workspace) / "artifacts/synthetic-traces/synthetic-traces.csv"
    artifact.write_text(artifact.read_text() + "tampered")
    assert client.post(f"{endpoint}/verify").json()["modified"] == ["synthetic-traces.csv"]
    artifact.unlink()
    assert client.post(f"{endpoint}/verify").json()["missing"] == ["synthetic-traces.csv"]


def test_malicious_manifest_cannot_read_outside_workspace(service):
    client, base, registry, workspace = service
    path = registry.root(workspace) / "results/synthetic-traces/manifest.json"
    payload = json.loads(path.read_text())
    payload["base_dir"] = "/etc"
    path.write_text(json.dumps(payload))
    assert client.post(f"{base}/results/synthetic-traces/verify").status_code == 400
    assert client.get(f"{base}/results").json()[0]["error"]
