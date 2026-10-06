"""Global Box access prepares real recordings without changing CSVs or results."""

import hashlib
import time
from types import SimpleNamespace as NS

import pytest
from gui.box_setup import BoxSetup
from gui.cropping import Cropping
from gui.csv_projects import Project, ProjectError
from gui.recordings import Recordings

from tests.test_gui_analysis import make_recording, payload
from tests.test_gui_box_setup import BoxFailure, FakeBox, finish


class DownloadBox(FakeBox):
    def __init__(self, files):
        super().__init__()
        self.files = files
        self.downloads = self
        self.downloaded = []
        self.fail_download = False
        self.unsafe = False

    def get_folder_items(self, number, **kwargs):
        self.calls.append(("items", number, kwargs))
        entries = [
            NS(id=str(i + 100), name=name, type="file", size=len(data), sha1=hashlib.sha1(data).hexdigest())
            for i, (name, data) in enumerate(self.files.items())
        ]
        if self.unsafe:
            entries[0].name = "../outside.avi"
        # Two pages, including a movie on the second page.
        return NS(
            entries=entries[1:] if kwargs.get("marker") else entries[:1],
            next_marker=None if kwargs.get("marker") else "page2",
        )

    def download_file_to_output_stream(self, number, output_stream):
        data = list(self.files.values())[int(number) - 100]
        output_stream.write(data[:4] if self.fail_download else data)
        if self.fail_download:
            raise BoxFailure(401)
        self.downloaded.append(number)


@pytest.fixture
def linked(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    make_recording(root)
    files = {p.name: p.read_bytes() for p in (root / "raw").iterdir()}
    for p in (root / "raw").iterdir():
        p.unlink()
    (root / "raw").rmdir()
    csv = root / "experiments.csv"
    csv.write_text(csv.read_text().replace("raw,,,", "raw,12,,"))
    project = Project.open(root)
    cache = tmp_path / "data"
    cache.mkdir()
    client = DownloadBox(files)
    box = BoxSetup(tmp_path / "settings", client_factory=lambda _: client)
    credentials = dict(method="ccg", client_id="client", client_secret="secret", subject_type="user", subject_id="8")
    finish(box, credentials, cache)
    return project, box, client, cache


def ready(service, project, **extra):
    status = service.prepare(project, payload(project, kind="compute", **extra))
    if status["state"] == "selection_required":
        status = service.start(
            project,
            payload(project, plan=status["plan"], files=[item["path"] for item in status["files"]], confirmed=True),
        )
    end = time.monotonic() + 10
    while status["state"] in {"queued", "downloading", "cancelling", "finalizing"} and time.monotonic() < end:
        time.sleep(0.01)
        status = service.status(project, status["id"])
    return status


def test_missing_box_recording_downloads_to_global_location_and_crops(linked):
    project, box, client, cache = linked
    original = (project.path / "experiments.csv").read_bytes()
    # Restart the app: saved credentials must suffice without the secret again.
    box = BoxSetup(box.config_path.parent, client_factory=lambda _: client)
    service = Recordings(box)
    result = ready(service, project)
    assert result["state"] == "ready", result
    assert result["recording_path"] == str(cache / "raw")
    assert set(p.name for p in (cache / "raw").iterdir()) >= set(client.files)
    preview = Cropping().preview(project, payload(project, data_path=result["data_path"]))
    assert (preview["width"], preview["height"]) == (32, 24)
    assert (project.path / "experiments.csv").read_bytes() == original
    assert ready(service, project)["state"] == "ready"
    assert len(client.downloaded) == len(client.files)


def test_explicit_base_folder_and_existing_results_are_preserved(linked, tmp_path):
    project, box, client, cache = linked
    target = tmp_path / "chosen"
    (target / "raw").mkdir(parents=True)
    result_file = target / "raw" / "results.txt"
    result_file.write_text("previous results")
    (target / "raw" / "0.avi").write_bytes(b"partial")
    result = ready(Recordings(box), project, data_path=str(target))
    assert result["state"] == "ready", result
    assert (target / "raw" / "0.avi").read_bytes() == client.files["0.avi"]
    assert result_file.read_text() == "previous results"
    assert list((target / "raw" / ".ace-box-backups").iterdir())


def test_failed_download_is_loud_and_does_not_publish_partial_files(linked):
    project, box, client, cache = linked
    client.fail_download = True
    result = ready(Recordings(box), project)
    assert result["state"] == "failed"
    assert "rejected or expired" in result["error"]
    assert "secret" not in str(result)
    assert not (cache / "raw" / "0.avi").exists()


def test_remote_path_traversal_is_rejected(linked):
    project, box, client, cache = linked
    client.unsafe = True
    with pytest.raises(ProjectError, match="unsafe"):
        ready(Recordings(box), project)
    assert not client.downloaded


def test_missing_folder_id_does_not_ask_for_credentials_if_connected(linked):
    project, box, client, cache = linked
    csv = project.path / "experiments.csv"
    csv.write_text(csv.read_text().replace("raw,12,,", "raw,,,"))
    project = Project.open(project.path)
    with pytest.raises(ProjectError, match="Calcium Box folder ID"):
        Recordings(box).prepare(project, payload(project))


def test_downloaded_recording_runs_the_existing_analysis(linked):
    from gui.runs import Runs

    from tests.test_gui_analysis import await_run

    project, box, client, cache = linked
    result = ready(Recordings(box), project)
    assert result["state"] == "ready"
    runs = Runs()
    reviewed = runs.review(project, payload(project, data_path=result["data_path"], kind="compute"))
    assert not reviewed["blockers"]
    started = runs.start(project, payload(project, review=reviewed["review"], confirmed=True))
    completed = await_run(runs, project, started)
    assert any("meanFluorescence" in item["name"] for item in completed["files"])


def test_nested_box_folders_and_absolute_recording_location(linked, tmp_path):
    project, box, client, cache = linked
    old = client.get_folder_items

    def listing(number, **kwargs):
        if number == "12":
            return NS(entries=[NS(id="13", name="Miniscope", type="folder")], next_marker=None)
        return old(number, **kwargs)

    client.get_folder_items = listing
    target = tmp_path / "absolute-recording"
    csv = project.path / "experiments.csv"
    csv.write_text(csv.read_text().replace("raw,12,,", f"{target},12,,"))
    project = Project.open(project.path)
    result = ready(Recordings(box), project)
    assert result["state"] == "ready", result
    assert result["recording_path"] == str(target)
    assert (target / "Miniscope" / "0.avi").read_bytes() == client.files["0.avi"]


def test_incomplete_receipt_is_repaired_without_redownloading_good_files(linked):
    project, box, client, cache = linked
    service = Recordings(box)
    assert ready(service, project)["state"] == "ready"
    client.downloaded.clear()
    (cache / "raw" / "0.avi").unlink()
    assert ready(service, project)["state"] == "ready"
    assert len(client.downloaded) == 1


def test_local_recording_works_without_box_configuration(tmp_path):
    root, _ = make_recording(tmp_path)
    project = Project.open(root)
    box = BoxSetup(
        tmp_path / "settings", client_factory=lambda _: pytest.fail("Local recordings need no authentication")
    )
    result = Recordings(box).prepare(project, payload(project))
    assert result["state"] == "ready" and result["data_path"] == str(root)


def test_http_download_and_crop_use_the_same_global_connection(linked):
    import threading

    from gui.server import ProjectServer

    from tests.test_gui_server import request

    project, box, client, cache = linked
    server = ProjectServer(("127.0.0.1", 0), str(project.path), box_setup=box)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, result = request(base, "/api/recording/prepare", payload(project, kind="crop"))
        assert status == 200
        assert result["state"] == "selection_required" and not client.downloaded
        status, result = request(
            base,
            "/api/recording/start",
            payload(project, plan=result["plan"], files=[item["path"] for item in result["files"]], confirmed=True),
        )
        assert status == 200
        while result["state"] in {"queued", "downloading", "cancelling", "finalizing"}:
            time.sleep(0.01)
            status, result = request(base, f"/api/recording?project={project.id}&job={result['id']}")
            assert status == 200
        assert result["state"] == "ready", result
        status, preview = request(base, "/api/crop/preview", payload(project, data_path=result["data_path"]))
        assert status == 200 and preview["width"] == 32
        status, folder = request(base, "/api/box/folders", {"folder": "12"})
        assert status == 200 and folder["id"] == "12"
        assert request(base, "/api/box/status")[1]["connected"]
        assert request(base, f"/api/recording?project=wrong&job={result['id']}")[0] == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_distinct_projects_share_account_but_use_their_own_folder_ids(linked, tmp_path):
    project, box, client, cache = linked
    calls = []

    def factory(credentials):
        calls.append(1)
        return client

    shared = BoxSetup(box.config_path.parent, client_factory=factory)
    service = Recordings(shared)
    assert ready(service, project)["state"] == "ready"
    second_root = tmp_path / "second-project"
    second_root.mkdir()
    (second_root / "experiments.csv").write_text(
        (project.path / "experiments.csv").read_text().replace("raw,12,,", "second-recording,99,,")
    )
    (second_root / "analysis_parameters.csv").write_text((project.path / "analysis_parameters.csv").read_text())
    second = Project.open(second_root)
    assert ready(service, second)["state"] == "ready"
    assert calls == [1]
    assert {call[1] for call in client.calls if call[0] == "items"} >= {"12", "99"}
    assert (cache / "raw" / "0.avi").is_file() and (cache / "second-recording" / "0.avi").is_file()


def test_another_box_recording_cannot_replace_a_managed_local_folder(linked):
    project, box, client, cache = linked
    service = Recordings(box)
    assert ready(service, project)["state"] == "ready"
    csv = project.path / "experiments.csv"
    csv.write_text(csv.read_text().replace("raw,12,,", "raw,99,,"))
    project = Project.open(project.path)
    with pytest.raises(ProjectError, match="another Box folder"):
        ready(service, project)


def test_confirmation_lists_size_and_prevents_unconfirmed_transfer(linked):
    project, box, client, cache = linked
    service = Recordings(box)
    plan = service.prepare(project, payload(project))
    assert plan["state"] == "selection_required"
    assert plan["total_bytes"] == sum(map(len, client.files.values()))
    assert plan["free_bytes"] > 0 and not client.downloaded
    for selection, confirmed in [(["0.avi"], False), (["../outside"], True), ([], True), (["0.avi", "0.avi"], True)]:
        with pytest.raises(ProjectError):
            service.start(project, payload(project, plan=plan["plan"], files=selection, confirmed=confirmed))
    assert not client.downloaded and not service.jobs


def await_download(service, project, job):
    deadline = time.monotonic() + 10
    while job["state"] in {"queued", "downloading", "cancelling", "finalizing"} and time.monotonic() < deadline:
        time.sleep(0.01)
        job = service.status(project, job["id"])
    return job


def test_single_movie_selection_is_remembered_without_fetching_the_rest(linked):
    project, box, client, cache = linked
    client.files["1.avi"] = client.files["0.avi"]
    service = Recordings(box)
    plan = service.plan(project, payload(project))
    result = await_download(
        service, project, service.start(project, payload(project, plan=plan["plan"], files=["0.avi"], confirmed=True))
    )
    assert result["state"] == "ready", result
    assert result["subset"]
    assert len(client.downloaded) == 1
    assert not (cache / "raw" / "1.avi").exists()
    # Another local AVI must not leak into the test's preview or private run inputs.
    (cache / "raw" / "1.avi").write_bytes(client.files["1.avi"])
    fresh = Recordings(box)
    assert fresh.prepare(project, payload(project))["selected_files"] == ["0.avi"]
    preview = Cropping().preview(project, payload(project, data_path=str(cache)))
    assert preview["total_files"] == 1
    from gui.runs import Runs

    reviewed = Runs().review(project, payload(project, data_path=str(cache), kind="compute"))
    assert [item["path"] for item in reviewed["files"]] == ["0.avi"]
    assert len(client.downloaded) == 1


def test_cancel_interrupts_stream_and_removes_only_staging(linked):
    import threading

    project, box, client, cache = linked
    (cache / "raw").mkdir()
    retained = cache / "raw" / "old-results.txt"
    retained.write_text("keep results")
    entered, release = threading.Event(), threading.Event()

    def transfer(number, output_stream):
        output_stream.write(b"part")
        entered.set()
        assert release.wait(5)
        output_stream.write(b"more")

    client.download_file_to_output_stream = transfer
    service = Recordings(box)
    plan = service.plan(project, payload(project))
    job = service.start(project, payload(project, plan=plan["plan"], files=["0.avi"], confirmed=True))
    assert entered.wait(5)
    result = service.cancel(project, payload(project, job=job["id"]))
    assert result["state"] == "cancelling"
    release.set()
    result = await_download(service, project, job)
    assert result["state"] == "cancelled", result
    assert not (cache / "raw" / "0.avi").exists()
    assert not list(cache.glob(".ace-box-download-*"))
    assert retained.read_text() == "keep results"
    assert service.cancel(project, payload(project, job=job["id"]))["state"] == "cancelled"


def test_subset_disk_check_does_not_require_space_for_the_whole_experiment(linked, monkeypatch):
    project, box, client, cache = linked
    original = client.get_folder_items

    def listing(number, **kwargs):
        page = original(number, **kwargs)
        if kwargs.get("marker"):
            page.entries.append(NS(id="999", name="huge.avi", type="file", size=50 * 1024**3, sha1=None))
        return page

    client.get_folder_items = listing
    monkeypatch.setattr("gui.recordings.shutil.disk_usage", lambda _: NS(free=2 * 1024**2))
    service = Recordings(box)
    plan = service.plan(project, payload(project))
    assert plan["total_bytes"] > 50 * 1024**3
    job = service.start(project, payload(project, plan=plan["plan"], files=["0.avi"], confirmed=True))
    result = await_download(service, project, job)
    assert result["state"] == "ready", result
    assert len(client.downloaded) == 1


def test_selection_changes_after_review_require_a_new_run_review(linked):
    import json

    from gui.runs import Runs

    project, box, client, cache = linked
    client.files["1.avi"] = client.files["0.avi"]
    service = Recordings(box)
    plan = service.plan(project, payload(project))
    selected = ["0.avi", "metaData.json", "timeStamps.csv"]
    job = service.start(project, payload(project, plan=plan["plan"], files=selected, confirmed=True))
    assert await_download(service, project, job)["state"] == "ready"
    (cache / "raw" / "1.avi").write_bytes(client.files["1.avi"])
    runs = Runs()
    reviewed = runs.review(project, payload(project, data_path=str(cache), kind="compute"))
    assert not reviewed["blockers"]
    receipt = cache / "raw" / ".ace-box.json"
    value = json.loads(receipt.read_text())
    value["selection"].append("1.avi")
    receipt.write_text(json.dumps(value))
    with pytest.raises(ProjectError, match="changed after review"):
        runs.start(project, payload(project, review=reviewed["review"], confirmed=True))


def test_confirmed_subset_runs_real_compute_without_copying_unselected_movies(linked):
    from pathlib import Path

    import numpy as np
    from gui.runs import Runs

    from tests.test_gui_analysis import await_run

    project, box, client, cache = linked
    client.files["1.avi"] = client.files["0.avi"]
    service = Recordings(box)
    plan = service.plan(project, payload(project))
    job = service.start(
        project, payload(project, plan=plan["plan"], files=["0.avi", "metaData.json", "timeStamps.csv"], confirmed=True)
    )
    assert await_download(service, project, job)["state"] == "ready"
    (cache / "raw" / "1.avi").write_bytes(client.files["1.avi"])
    runs = Runs()
    reviewed = runs.review(project, payload(project, data_path=str(cache), kind="compute"))
    result = await_run(runs, project, runs.start(project, payload(project, review=reviewed["review"], confirmed=True)))
    root = Path(result["directory"])
    assert not (root / "recording" / "1.avi").exists()
    with np.load(root / "calcium_signals" / "meanFluorescence_1.npz") as values:
        assert values["meanFluorescence"].shape == (20,)


def test_stale_download_plan_does_not_start_any_transfer(linked):
    project, box, client, cache = linked
    service = Recordings(box)
    plan = service.plan(project, payload(project))
    csv = project.path / "experiments.csv"
    csv.write_text(csv.read_text().replace("Test subject", "Updated subject"))
    with pytest.raises(ProjectError, match="changed"):
        service.start(project, payload(project, plan=plan["plan"], files=["0.avi"], confirmed=True))
    assert not client.downloaded and not service.jobs
