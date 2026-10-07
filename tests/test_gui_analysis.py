"""Run real pipelines on small temporary recordings and verify crop/results safety."""

import csv
import json
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from gui.cropping import Cropping, validate_coords
from gui.csv_projects import Project, ProjectError
from gui.run_specs import effective_parameters
from gui.runs import Runs


def make_recording(root):
    recording = root / "raw"
    recording.mkdir(parents=True)
    writer = cv2.VideoWriter(str(recording / "0.avi"), cv2.VideoWriter_fourcc(*"FFV1"), 10, (32, 24), False)
    assert writer.isOpened()
    frames = []
    for index in range(20):
        image = (np.arange(24)[:, None] * 5 + np.arange(32)[None, :] + index).astype(np.uint8)
        frames.append(image)
        writer.write(image)
    writer.release()
    (recording / "metaData.json").write_text(json.dumps({"frameRate": 10}))
    (recording / "timeStamps.csv").write_text(
        "Frame Number,Time Stamp (ms),Buffer Index\n" + "".join(f"{i},{i * 100},0\n" for i in range(20))
    )
    columns = [
        "line number",
        "id",
        "date (YYMMDD)",
        "calcium imaging directory",
        "Box Calcium Folder ID",
        "ephys directory",
        "Box ephys folder ID",
    ]
    with (root / "experiments.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerow(["1", "Test subject", "261005", "raw", "", "", ""])
    (root / "analysis_parameters.csv").write_text('line number,crop,unknown_lab_field\n1,"(2, 3, 20, 15)",keep\n')
    return root, frames


@pytest.fixture
def recording(tmp_path):
    return make_recording(tmp_path)


def payload(project, **extra):
    return {"number": "1", "project": project.id, "versions": project.digests, **extra}


def await_run(service, project, run):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        detail = service.inspect(project, run["id"])
        if detail["state"] != "running":
            assert detail["state"] == "completed", detail["log"]
            return detail
        time.sleep(0.05)
    service.stop(project, run["id"])
    pytest.fail("Small fixture run exceeded 45 seconds")


def test_preview_saves_canonical_coords_without_altering_legacy_or_other_records(recording):
    root, frames = recording
    project = Project.open(root)
    original = (root / "analysis_parameters.csv").read_bytes()
    crop = Cropping()
    preview = crop.preview(project, payload(project))
    assert preview["coords"] == [2, 3, 20, 15] and preview["legacy"]
    assert preview["width"] == 32 and preview["height"] == 24
    saved, backup = crop.save(project, payload(project, preview=preview["preview"], coords=[4, 5, 22, 18]))
    assert saved.parameters["1"]["crop_coords"] == "(4, 5, 22, 18)"
    assert saved.parameters["1"]["crop"] == "(2, 3, 20, 15)"
    assert saved.parameters["1"]["unknown_lab_field"] == "keep"
    assert Path(backup).read_bytes() == original
    with pytest.raises(ProjectError):
        crop.save(saved, payload(saved, preview=preview["preview"], coords=[0, 0, 32, 24]))


def test_crop_bounds_are_not_silently_clamped():
    for coords in [[1, 2, 1, 5], [-1, 0, 5, 5], [0, 0, 33, 24], [0.5, 0, 5, 5]]:
        with pytest.raises(ProjectError):
            validate_coords(coords, 32, 24)


def test_review_uses_saved_csv_defaults_and_headless_policy(recording):
    root, frames = recording
    project = Project.open(root)
    params, sources = effective_parameters(
        "miniscope",
        {
            "n_processes": "2",
            "run_CNMFE": "False",
            "remove_components_with_gui": "True",
            "crop_coords": "(1, 2, 10, 12)",
        },
    )
    assert params["n_processes"] == 2 and not params["run_CNMFE"]
    assert params["remove_components_with_gui"] is False
    assert sources["n_processes"] == "Saved CSV"
    review = Runs().review(project, payload(project, kind="compute"))
    assert not review["blockers"]
    assert review["parameters"]["crop_coords"] == [2, 3, 20, 15]
    assert review["metadata"]["id"] == "Test subject"


def test_confirmation_and_stale_review_block_execution(recording):
    root, frames = recording
    project = Project.open(root)
    runs = Runs()
    review = runs.review(project, payload(project))
    with pytest.raises(ProjectError, match="confirm"):
        runs.start(project, {"review": review["review"]})
    changed, _ = project.save("1", "parameters", {"unknown_lab_field": "changed"}, project.digests)
    with pytest.raises(ProjectError, match="changed after review"):
        runs.start(changed, {"review": review["review"], "confirmed": True})
    assert not (root / ".ace-runs").exists()


def test_cnmfe_review_names_exact_destinations_and_respects_disabled_outputs(recording):
    root, frames = recording
    project = Project.open(root)
    runs = Runs()
    review = runs.review(project, payload(project, kind="miniscope"))
    directory = Path(review["directory"])
    assert directory.parent == root / ".ace-runs" and not directory.exists()
    assert review["destinations"]["Neuron estimates"] == str(directory / "recording/saved_movies/estimates.hdf5")
    assert review["destinations"]["Run log"] == str(directory / "run.log")
    project.parameters["1"]["save_CNMFE_estimates_filename"] = "estimates.h5"
    incompatible = runs.review(project, payload(project, kind="miniscope"))
    assert any("must end in .hdf5" in message for message in incompatible["blockers"])
    project.parameters["1"]["save_estimates"] = "False"
    review = runs.review(project, payload(project, kind="miniscope"))
    assert "Neuron estimates" not in review["destinations"]


def test_changed_recording_and_missing_data_block_execution(recording):
    root, frames = recording
    project = Project.open(root)
    runs = Runs()
    review = runs.review(project, payload(project))
    (root / "raw" / "metaData.json").write_text('{"frameRate":20}')
    with pytest.raises(ProjectError, match="Recording files changed"):
        runs.start(project, {"review": review["review"], "confirmed": True})
    project.experiments["1"]["calcium imaging directory"] = "missing"
    bad = runs.review(project, payload(project))
    assert any("unavailable" in item for item in bad["blockers"])
    with pytest.raises(ProjectError, match="Resolve"):
        runs.start(project, {"review": bad["review"], "confirmed": True})


def test_real_compute_rerun_preserves_results_and_original_csvs(recording):
    pytest.importorskip("caiman")
    root, frames = recording
    project = Project.open(root)
    csvs = {name: (root / name).read_bytes() for name in ["experiments.csv", "analysis_parameters.csv"]}
    raw = (root / "raw" / "0.avi").read_bytes()
    runs = Runs()
    review = runs.review(project, payload(project))
    first = await_run(runs, project, runs.start(project, {"review": review["review"], "confirmed": True}))
    assert first["directory"] == review["directory"]
    first_output = Path(first["directory"]) / "calcium_signals" / "meanFluorescence_1.npz"
    actual = np.load(first_output)["meanFluorescence"]
    expected = np.asarray(frames)[:, 24 - 15 : 24 - 3, 2:20].mean(axis=(1, 2))
    np.testing.assert_allclose(actual, expected)
    original_result = first_output.read_bytes()
    review = runs.review(project, payload(project))
    second = await_run(runs, project, runs.start(project, {"review": review["review"], "confirmed": True}))
    assert first["directory"] != second["directory"]
    assert first_output.read_bytes() == original_result
    assert all((root / name).read_bytes() == value for name, value in csvs.items())
    assert (root / "raw" / "0.avi").read_bytes() == raw
    assert len(Runs().listing(project, "1")["runs"]) == 2
    assert first["output_inventory"]["kind"] == "compute"
    assert any(
        item["name"] == "mean_fluorescence" and item["status"] == "exported"
        for item in first["output_inventory"]["outputs"]
    )


def test_real_cropped_movie_uses_core_preprocessor(recording):
    pytest.importorskip("caiman")
    root, frames = recording
    project = Project.open(root)
    runs = Runs()
    review = runs.review(project, payload(project, kind="preprocess"))
    result = await_run(runs, project, runs.start(project, {"review": review["review"], "confirmed": True}))
    movie = Path(result["directory"]) / "recording" / "saved_movies" / "preprocessed.avi"
    cap = cv2.VideoCapture(str(movie))
    try:
        assert int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) == 18
        assert int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) == 12
        assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == 20
    finally:
        cap.release()
    assert any(item["name"] == "recording/saved_movies/preprocessed.avi" for item in result["files"])
    assert result["output_inventory"]["kind"] == "preprocess"
    with np.load(Path(result["directory"]) / "preprocessing.npz", allow_pickle=False) as arrays:
        assert arrays["projection_time"].shape == (20,) and arrays["frame_rate"] == 10


def test_crop_settings_do_not_leak_into_ephys_arguments():
    params, _ = effective_parameters("ephys", {"crop_coords": "(1,2,20,30)", "crop": "True"})
    assert "crop_coords" not in params and "crop" not in params


def test_invalid_numeric_run_settings_and_out_of_bounds_crop_block_review(recording):
    root, frames = recording
    project = Project.open(root)
    project, _ = project.save(
        "1", "parameters", {"crop_coords": "(0,0,40,30)"}, project.digests, new_columns=("crop_coords",)
    )
    review = Runs().review(project, payload(project))
    assert any("fit inside" in item for item in review["blockers"])
    from gui.run_specs import validate_settings

    for changes in [{"run_CNMFE": "maybe"}, {"n_processes": "0"}, {"n_processes": "2.5"}]:
        with pytest.raises(ValueError):
            validate_settings("miniscope", changes)


def test_runtime_failure_is_reported_and_inputs_remain_saved(recording):
    pytest.importorskip("caiman")
    root, frames = recording
    # A deliberately incomplete recording passes the AVI check but fails core timestamp loading.
    (root / "raw" / "timeStamps.csv").unlink()
    project = Project.open(root)
    runs = Runs()
    review = runs.review(project, payload(project))
    run = runs.start(project, {"review": review["review"], "confirmed": True})
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        detail = runs.inspect(project, run["id"])
        if detail["state"] != "running":
            break
        time.sleep(0.05)
    assert detail["state"] == "failed"
    assert detail["exit_code"] != 0 and detail["error"]
    assert "SKIPPED" in detail["log"]
    assert (Path(detail["directory"]) / "experiments.csv").exists()
    assert (root / "raw" / "0.avi").exists()
