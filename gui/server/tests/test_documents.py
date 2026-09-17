import json


def test_edit_validate_conflict_and_persist(service):
    client, base, registry, workspace = service
    path = "parameters/analysis.cnmfe.json"
    original = client.get(f"{base}/document", params={"path": path}).json()
    value = json.loads(original["text"])
    value["params"]["min_corr"] = 0.91
    payload = {"path": path, "text": json.dumps(value), "etag": original["etag"]}
    saved = client.put(f"{base}/document", json=payload)
    assert saved.status_code == 200
    assert json.loads((registry.root(workspace) / path).read_text())["params"]["min_corr"] == 0.91
    assert client.put(f"{base}/document", json=payload).status_code == 409
    payload["etag"] = saved.json()["etag"]
    value["params"]["min_corr"] = "invalid number"
    payload["text"] = json.dumps(value)
    assert client.put(f"{base}/document", json=payload).status_code == 400
    assert json.loads((registry.root(workspace) / path).read_text())["params"]["min_corr"] == 0.91


def test_reject_nonfinite_and_provenance_edits(service):
    client, base, _, _ = service
    path = "parameters/analysis.cnmfe.json"
    doc = client.get(f"{base}/document", params={"path": path}).json()
    for text in ('{"x": NaN}', "[]", "{broken"):
        assert client.put(f"{base}/document", json={"path": path, "etag": doc["etag"], "text": text}).status_code == 400
    value = json.loads(doc["text"])
    value["_csv"]["raw"]["untrusted"] = "changed"
    assert (
        client.put(f"{base}/document", json={"path": path, "etag": doc["etag"], "text": json.dumps(value)}).status_code
        == 400
    )


def test_historical_read_and_multiple_workspaces(service):
    client, base, _, _ = service
    assert len(client.get("/api/session").json()["workspaces"]) == 2
    revisions = client.get(f"{base}/history").json()
    doc = client.get(
        f"{base}/document", params={"path": "parameters/analysis.cnmfe.json", "revision": revisions[-1]["oid"]}
    ).json()
    assert json.loads(doc["text"])["params"]["min_corr"] == 0.8
