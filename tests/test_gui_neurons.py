"""Real CaImAn load/select/save parity, provenance, resumable decisions and traces."""

import base64
import io
import json
import time
from pathlib import Path

import numpy as np
import pytest
from gui.csv_projects import Project, ProjectError
from gui.neurons import Neurons, load_estimates, trace_points
from PIL import Image
from scipy.sparse import csc_matrix


@pytest.fixture
def estimates(tmp_path):
    from caiman.source_extraction.cnmf.cnmf import CNMF
    from caiman.source_extraction.cnmf.estimates import Estimates

    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "experiments.csv").write_text("line number,id\n1,Rat 1\n")
    (project_root / "analysis_parameters.csv").write_text("line number,crop\n1,False\n")
    dims = (24, 32)
    yy, xx = np.mgrid[:24, :32]
    A = csc_matrix(
        np.column_stack(
            [
                np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / 8).reshape(-1, order="F")
                for x, y in [(5, 5), (16, 12), (25, 18)]
            ]
        )
    )
    C = np.zeros((3, 600), dtype=np.float32)
    C[0, 10], C[1, 300], C[2, 580] = 10, 20, 30
    obj = CNMF(n_processes=1)
    obj.dims = dims
    obj.estimates = Estimates(A=A, C=C, dims=dims)
    obj.estimates.g = np.zeros((3, 2))  # Fitted estimates carry per-neuron AR coefficients.
    obj.params.set("data", {"fr": 10})
    path = tmp_path / "estimates.hdf5"
    obj.save(str(path))
    return Project.open(project_root), path, A, C


def body(project, **extra):
    return {"project": project.id, "number": "1", **extra}


def decide(service, project, session, index, value):
    return service.decide(
        project,
        body(
            project,
            session=session["session"],
            revision=session["revision"],
            index=index,
            decision=value,
            current=min(index + 1, 2),
        ),
    )


def wait_export(service, project, job):
    end = time.monotonic() + 20
    while job["state"] == "saving" and time.monotonic() < end:
        time.sleep(0.02)
        job = service.export_status(project, job["id"])
    assert job["state"] == "saved", job["message"]
    return job


def test_load_footprints_traces_peak_window_and_frame_override(estimates):
    project, path, A, C = estimates
    service = Neurons()
    session = service.open(project, body(project, path=str(path)))
    assert session["dims"] == [24, 32] and session["count"] == 3 and session["fr"] == 10
    detail = service.component(project, body(project, session=session["session"], index=1, window=10))
    assert detail["peak_pixel"] == [16, 12]
    assert (detail["start"], detail["end"]) == (25, 35)
    assert [30, 20] in detail["trace"]
    edge = service.component(project, body(project, session=session["session"], index=0, window=30, fr=20))
    assert edge["start"] == 0 and edge["end"] == 29.95 and edge["fr"] == 20
    assert edge["background"] if "background" in edge else session["background"]
    assert edge["footprint"]


def test_footprint_images_match_script_sum_and_fortran_reshape(estimates):
    from matplotlib import colormaps

    project, path, A, C = estimates
    service = Neurons()
    session = service.open(project, body(project, path=str(path)))
    detail = service.component(project, body(project, session=session["session"], index=2))

    def decoded(encoded):
        return np.asarray(Image.open(io.BytesIO(base64.b64decode(encoded))))

    summed = A.toarray().sum(axis=1).reshape((24, 32), order="F")
    selected = A.toarray()[:, 2].reshape((24, 32), order="F")
    expected_bg = (colormaps["inferno"](summed / (summed.max() + 1e-9)) * 255).astype(np.uint8)
    expected_fp = (colormaps["hot"](selected / (selected.max() + 1e-9)) * 255).astype(np.uint8)
    np.testing.assert_array_equal(decoded(session["background"]), expected_bg)
    np.testing.assert_array_equal(decoded(detail["footprint"]), expected_fp)
    outline = decoded(detail["outline"])
    support = selected >= selected.max() * 0.2
    np.testing.assert_array_equal(outline[:, :, 3] > 0, support)
    assert np.any(outline[:, :, 3] == 255)
    assert np.any(outline[:, :, 3] == 50)
    assert detail["peak_pixel"] == [25, 18]


@pytest.mark.parametrize(
    "index,window,expected",
    [(0, 10, (0, 10)), (1, 10, (25, 35)), (2, 30, (29.9, 59.9))],
)
def test_peak_window_extends_at_both_edges(estimates, index, window, expected):
    project, path, A, C = estimates
    service = Neurons()
    session = service.open(project, body(project, path=str(path)))
    detail = service.component(project, body(project, session=session["session"], index=index, window=window))
    assert (detail["start"], detail["end"]) == pytest.approx(expected)
    assert detail["peak_s"] == pytest.approx([1, 30, 58][index])
    assert [detail["peak_s"], float(C[index].max())] in detail["trace"]


def test_trace_pan_full_view_and_frame_rate_use_unmodified_c(estimates):
    project, path, A, C = estimates
    service = Neurons()
    session = service.open(project, body(project, path=str(path), window=10))
    request = body(project, session=session["session"], index=1, fr=20, window=10)
    moved = service.component(project, request | {"start": 999})
    assert (moved["start"], moved["end"]) == pytest.approx((19.95, 29.95))
    assert [15, 20] not in moved["trace"]
    peak = service.component(project, request)
    assert (peak["start"], peak["end"]) == pytest.approx((10, 20))
    assert [15, 20] in peak["trace"]
    full = service.component(project, request | {"full": True})
    assert (full["start"], full["end"], full["window"]) == pytest.approx((0, 29.95, 10))
    assert full["trace"] == [[i / 20, float(value)] for i, value in enumerate(C[1])]
    assert service.open(project, body(project, path=str(path)))["fr"] == 20


def test_keep_reject_navigation_bulk_and_resume_preserve_explicit_choices(estimates):
    project, path, A, C = estimates
    service = Neurons()
    session = service.open(project, body(project, path=str(path)))
    kept = decide(service, project, session, 0, True)
    assert kept["current"] == 1 and (kept["kept"], kept["undecided"]) == (1, 2)
    rejected = decide(service, project, kept, 2, False)
    assert rejected["current"] == 2 and rejected["decisions"] == [True, None, False]
    filled = service.decide(
        project,
        body(
            project,
            session=session["session"],
            revision=rejected["revision"],
            bulk="reject",
        ),
    )
    assert filled["decisions"] == [True, False, False]
    assert (filled["kept"], filled["rejected"], filled["undecided"]) == (1, 2, 0)
    resumed = Neurons().open(project, body(project, path=str(path)))
    assert resumed["decisions"] == filled["decisions"] and resumed["current"] == 2
    restored = decide(service, project, filled, 2, None)
    assert restored["decisions"] == [True, False, None]


def test_decisions_resume_clear_and_reject_stale_tabs(estimates):
    project, path, A, C = estimates
    service = Neurons()
    opened = service.open(project, body(project, path=str(path)))
    saved = decide(service, project, opened, 0, True)
    with pytest.raises(ProjectError, match="another tab"):
        decide(service, project, opened, 1, False)
    with pytest.raises(ProjectError, match="another tab"):
        service.component(
            project, body(project, session=opened["session"], revision=opened["revision"], index=0, fr=20)
        )
    saved = decide(service, project, saved, 1, False)
    fresh = Neurons().open(project, body(project, path=str(path)))
    assert fresh["decisions"] == [True, False, None]
    cleared = decide(service, project, saved, 0, None)
    assert cleared["decisions"] == [None, False, None]
    assert path.is_file()


def test_done_requires_explicit_undecided_choice_and_exports_original_ids(estimates):
    project, path, A, C = estimates
    original = path.read_bytes()
    service = Neurons()
    session = service.open(project, body(project, path=str(path)))
    session = decide(service, project, session, 1, False)
    with pytest.raises(ProjectError, match="undecided"):
        service.export(project, body(project, session=session["session"], revision=session["revision"], confirmed=True))
    session = service.decide(
        project, body(project, session=session["session"], revision=session["revision"], bulk="keep")
    )
    assert session["decisions"] == [True, False, True]
    job = wait_export(
        service,
        project,
        service.export(
            project, body(project, session=session["session"], revision=session["revision"], confirmed=True)
        ),
    )
    folder = Path(job["directory"])
    curated = load_estimates(folder / "estimates_curated.hdf5")
    np.testing.assert_array_equal(curated.estimates.C, C[[0, 2]])
    np.testing.assert_allclose(curated.estimates.A.toarray(), A.toarray()[:, [0, 2]])
    with np.load(folder / "C_curated.npz") as data:
        assert data["neuron_ids"].tolist() == [0, 2]
        assert data["fr"].item() == 10
        np.testing.assert_array_equal(data["C"], C[[0, 2]])
        np.testing.assert_allclose(data["A_dense"], A.toarray()[:, [0, 2]])
    assert path.read_bytes() == original
    assert service.component(project, body(project, session=session["session"], index=2))["count"] == 3
    second = wait_export(
        service,
        project,
        service.export(
            project, body(project, session=session["session"], revision=session["revision"], confirmed=True)
        ),
    )
    assert second["directory"] != job["directory"]


def test_all_rejected_keeps_a_decision_record_without_invalid_empty_estimates(estimates):
    project, path, A, C = estimates
    service = Neurons()
    session = service.open(project, body(project, path=str(path)))
    session = service.decide(
        project, body(project, session=session["session"], revision=session["revision"], bulk="reject")
    )
    job = wait_export(
        service,
        project,
        service.export(
            project, body(project, session=session["session"], revision=session["revision"], confirmed=True)
        ),
    )
    assert job["files"] == ["decisions.json"]
    assert json.loads((Path(job["directory"]) / "decisions.json").read_text())["decisions"] == [False] * 3


@pytest.mark.parametrize(
    "derivative,peaks",
    [
        ("zeroth", [10, 580]),
        ("first", [9, 579]),
        ("second", [8, 578]),
    ],
)
def test_curated_export_recomputes_events_only_for_kept_neurons(estimates, derivative, peaks):
    project, path, A, C = estimates
    original = path.read_bytes()
    service = Neurons()
    session = service.open(project, body(project, path=str(path)))
    session = decide(service, project, session, 1, False)
    session = service.decide(
        project, body(project, session=session["session"], revision=session["revision"], bulk="keep")
    )
    outputs = []
    # A second derivative has two positive peaks around each impulse.
    event_lists = [[index, index + 2] if derivative == "second" else [index] for index in peaks]
    for height, expected in [(5, dict(zip(["0", "1"], event_lists))), (25, {"0": [], "1": event_lists[1]})]:
        job = wait_export(
            service,
            project,
            service.export(
                project,
                body(
                    project,
                    session=session["session"],
                    revision=session["revision"],
                    confirmed=True,
                    event_analysis={"derivative": derivative, "event_height": height},
                ),
            ),
        )
        folder = Path(job["directory"])
        events = json.loads((folder / "calcium-events.json").read_text())
        assert events["ca_events_idx"] == expected
        assert events["neuron_ids"] == [0, 2]
        assert events["parameters"] == {"derivative": derivative, "event_height": height}
        assert events["fr"] == 10
        assert events["estimates"]["path"] == str(folder / "estimates_curated.hdf5")
        assert events["source"] == json.loads((folder / "decisions.json").read_text())["source"]
        outputs.append((folder / "calcium-events.json", events))
    assert outputs[0][0] != outputs[1][0]
    assert json.loads(outputs[0][0].read_text()) == outputs[0][1]
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "settings",
    [
        False,
        {},
        {"derivative": []},
        {"derivative": "third", "event_height": 5},
        *[
            {"derivative": "first", "event_height": value}
            for value in [None, True, "", "bad", float("nan"), float("inf")]
        ],
    ],
)
def test_invalid_event_settings_do_not_create_an_export(estimates, settings):
    project, path, A, C = estimates
    service = Neurons()
    session = service.open(project, body(project, path=str(path)))
    session = service.decide(
        project,
        body(
            project,
            session=session["session"],
            revision=session["revision"],
            bulk="keep",
        ),
    )
    with pytest.raises(ProjectError):
        service.export(
            project,
            body(
                project,
                session=session["session"],
                revision=session["revision"],
                confirmed=True,
                event_analysis=settings,
            ),
        )
    assert not (project.path / ".ace-curations").exists()


def test_event_detection_failure_retains_source_and_review_without_partial_export(estimates, monkeypatch):
    from aceneurotools.miniscope.miniscope_postprocessor import MiniscopePostprocessor

    project, path, A, C = estimates
    original = path.read_bytes()
    service = Neurons()
    session = service.open(project, body(project, path=str(path)))
    session = service.decide(
        project,
        body(
            project,
            session=session["session"],
            revision=session["revision"],
            bulk="keep",
        ),
    )

    def fail(*args, **kwargs):
        raise RuntimeError("detector failed")

    monkeypatch.setattr(MiniscopePostprocessor, "find_calcium_events_with_derivatives", fail)
    job = service.export(
        project,
        body(
            project,
            session=session["session"],
            revision=session["revision"],
            confirmed=True,
            event_analysis={"derivative": "first", "event_height": 5},
        ),
    )
    end = time.monotonic() + 20
    while job["state"] == "saving" and time.monotonic() < end:
        time.sleep(0.02)
        job = service.export_status(project, job["id"])
    assert job["state"] == "failed" and "detector failed" in job["message"]
    assert not Path(job["directory"]).exists()
    assert path.read_bytes() == original
    assert json.loads(Path(session["review_path"]).read_text())["decisions"] == [True] * 3


def test_event_controls_use_saved_settings_and_export_reviewed_frame_rate(estimates):
    project, path, A, C = estimates
    (project.path / "analysis_parameters.csv").write_text(
        "line number,crop,derivative_for_estimates,event_height\n1,False,zeroth,12\n"
    )
    project = Project.open(project.path)
    service = Neurons()
    session = service.open(project, body(project, path=str(path), fr=20))
    assert session["event_parameters"] == {"derivative": "zeroth", "event_height": 12}
    session = service.decide(
        project,
        body(
            project,
            session=session["session"],
            revision=session["revision"],
            bulk="keep",
        ),
    )
    job = wait_export(
        service,
        project,
        service.export(
            project,
            body(
                project,
                session=session["session"],
                revision=session["revision"],
                confirmed=True,
                event_analysis=session["event_parameters"],
            ),
        ),
    )
    folder = Path(job["directory"])
    events = json.loads((folder / "calcium-events.json").read_text())
    assert events["fr"] == 20 and events["frames"] == 600
    assert events["ca_events_idx"] == {"0": [], "1": [300], "2": [580]}
    assert load_estimates(folder / "estimates_curated.hdf5").params.get("data", "fr") == 20


def test_latest_estimates_are_scoped_to_experiment_and_completed_runs(estimates, tmp_path):
    import os
    import shutil

    project, path, A, C = estimates
    project.experiments["1"]["calcium imaging directory"] = str(path.parent)
    saved = path.parent / "saved_movies"
    saved.mkdir()
    recent = saved / "estimates.hdf5"
    shutil.copyfile(path, recent)
    os.utime(path, ns=(100, 100))
    os.utime(recent, ns=(200, 200))
    service = Neurons()
    assert service.sources(project, "1")["latest"] == str(recent)
    completed = tmp_path / "completed"
    completed.mkdir()
    newest = completed / "run_estimates.hdf5"
    shutil.copyfile(path, newest)
    runs = {
        "runs": [
            {"kind": "miniscope", "state": "completed", "directory": str(completed), "files": [{"name": newest.name}]}
        ]
    }
    assert service.sources(project, "1", runs=runs)["latest"] == str(newest)
    runs["runs"][0]["state"] = "running"
    assert service.sources(project, "1", runs=runs)["latest"] == str(recent)


def test_named_exports_never_replace_original_even_in_its_folder(estimates):
    project, path, A, C = estimates
    original = path.read_bytes()
    service = Neurons()
    session = service.open(project, body(project, path=str(path)))
    session = service.decide(
        project, body(project, session=session["session"], revision=session["revision"], bulk="keep")
    )
    for name in ["../estimates.hdf5", "folder/file.h5", "notes.txt"]:
        with pytest.raises(ProjectError, match="filename"):
            service.export(
                project,
                body(project, session=session["session"], revision=session["revision"], confirmed=True, filename=name),
            )
    for name in ["researcher_review.hdf5", "researcher_review.h5", "review.HDF5", path.name]:
        job = wait_export(
            service,
            project,
            service.export(
                project,
                body(
                    project,
                    session=session["session"],
                    revision=session["revision"],
                    confirmed=True,
                    filename=name,
                    output_path=str(path.parent),
                ),
            ),
        )
        assert (Path(job["directory"]) / name).exists()
        assert load_estimates(Path(job["directory"]) / name).estimates.C.shape == C.shape
        assert Path(job["directory"]) / name != path
        assert path.read_bytes() == original


def test_changed_input_and_invalid_parameters_fail_without_altering_data(estimates):
    project, path, A, C = estimates
    service = Neurons()
    session = service.open(project, body(project, path=str(path)))
    for fr in [0, -1, float("nan")]:
        with pytest.raises(ProjectError):
            service.open(project, body(project, path=str(path), fr=fr))
        with pytest.raises(ProjectError):
            service.component(project, body(project, session=session["session"], index=1, fr=fr))
    path.touch()
    with pytest.raises(ProjectError, match="changed"):
        decide(service, project, session, 0, True)


def test_full_trace_keeps_the_review_window_and_invalid_journal_is_retained(estimates):
    project, path, A, C = estimates
    service = Neurons()
    session = service.open(project, body(project, path=str(path), window=5))
    detail = service.component(project, body(project, session=session["session"], index=1, full=True))
    assert detail["start"] == 0 and detail["end"] == 59.9 and detail["window"] == 5
    saved = json.loads(Path(session["review_path"]).read_text())
    assert saved["window"] == 5
    saved["current"] = -1
    Path(session["review_path"]).write_text(json.dumps(saved))
    with pytest.raises(ProjectError, match="saved review is invalid"):
        Neurons().open(project, body(project, path=str(path)))
    assert json.loads(Path(session["review_path"]).read_text())["current"] == -1


def test_trace_envelope_retains_a_narrow_peak():
    values = np.zeros(100_000)
    values[50001] = 99
    points = trace_points(values, 10, limit=1000)
    assert len(points) <= 1000 and [5000.1, 99] in points


def test_neuron_http_and_estimates_file_browser(estimates):
    import threading

    from gui.server import ProjectServer

    from tests.test_gui_server import request

    project, path, A, C = estimates
    server = ProjectServer(("127.0.0.1", 0), str(project.path))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        assert request(base, "/api/health")[1]["application"] == "ACE Experiments"
        status, listing = request(base, f"/api/folders?path={path.parent}&files=estimates")
        assert status == 200 and any(item["path"] == str(path) for item in listing["files"])
        assert request(base, "/api/neuron/open", body(project, path=str(path)))[0] == 200
        opened = request(base, "/api/neuron/open", body(project, path=str(path)))[1]
        status, result = request(base, "/api/neuron/component", body(project, session=opened["session"], index=0))
        assert status == 200 and result["peak_pixel"] == [5, 5]
        assert (
            request(
                base,
                "/api/neuron/decide",
                body(project, session=opened["session"], revision=result["revision"], index=0, decision=True),
            )[0]
            == 200
        )
        status, opened = request(base, "/api/neuron/open", body(project, path=str(path)))
        assert status == 200
        status, completed = request(
            base,
            "/api/neuron/decide",
            body(
                project,
                session=opened["session"],
                revision=opened["revision"],
                bulk="keep",
            ),
        )
        assert status == 200
        status, job = request(
            base,
            "/api/neuron/export",
            body(
                project,
                session=opened["session"],
                revision=completed["revision"],
                confirmed=True,
                event_analysis={"derivative": "zeroth", "event_height": 5},
            ),
        )
        assert status == 200
        job = wait_export(server.neurons, project, job)
        status, result = request(base, f"/api/neuron/export?project={project.id}&job={job['id']}")
        assert status == 200 and "calcium-events.json" in result["files"]
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
