import json


def test_real_record_diff_restore_and_recovery(service):
    client, base, registry, workspace = service
    initial = client.get(f"{base}/history").json()
    path = "parameters/analysis.cnmfe.json"
    doc = client.get(f"{base}/document", params={"path": path}).json()
    changed = json.loads(doc["text"])
    changed["params"]["min_corr"] = 0.94
    assert client.put(f"{base}/document", json={"path": path, "text": json.dumps(changed), "etag": doc["etag"]}).status_code == 200
    version = client.get(f"{base}/state").json()["status"]["version"]
    saved = client.post(f"{base}/record", json={"message": "Reviewed threshold", "version": version})
    assert saved.status_code == 200
    revision = saved.json()["revision"]
    differences = client.get(f"{base}/diff", params={"a": initial[0]["oid"], "b": revision}).json()
    assert any(c["key"] == "params.min_corr" for d in differences for c in d["param_changes"])
    # A dirty disk edit is preserved in a real EVC safety snapshot.
    changed["params"]["min_corr"] = 0.97
    (registry.root(workspace) / path).write_text(json.dumps(changed))
    version = client.get(f"{base}/state").json()["status"]["version"]
    restored = client.post(f"{base}/restore", json={"revision": initial[-1]["oid"], "version": version}).json()
    assert restored["safety_snapshot"]
    assert registry.evc(workspace).show().oid == revision  # HEAD never rewinds
    assert json.loads((registry.root(workspace) / path).read_text())["params"]["min_corr"] == 0.8
    journal = client.get(f"{base}/recovery").json()
    assert any(e["new"] == restored["safety_snapshot"] for e in journal)
    safety = client.get(f"{base}/document", params={"path": path, "revision": restored["safety_snapshot"]}).json()
    assert json.loads(safety["text"])["params"]["min_corr"] == 0.97


def test_stale_review_is_rejected_and_comments_preserve_history(service):
    client, base, registry, workspace = service
    state = client.get(f"{base}/state").json()["status"]
    path = registry.root(workspace) / "parameters/analysis.cnmfe.json"
    path.write_text(path.read_text() + "\n")
    assert client.post(f"{base}/record", json={"message": "stale", "version": state["version"]}).status_code == 409
    assert client.post(f"{base}/restore", json={"revision": "HEAD", "version": state["version"]}).status_code == 409
    before = client.get(f"{base}/history").json()
    assert client.post(f"{base}/revision/HEAD/comments", json={"text": "Reviewed with lab"}).status_code == 200
    assert "Reviewed with lab" in client.get(f"{base}/revision/HEAD/comments").json()["text"]
    assert client.get(f"{base}/history").json() == before
