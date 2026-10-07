"""Subprocess adapter. Run the existing pipeline APIs against private run inputs."""

from __future__ import annotations

import json
import os
import shutil
import sys
import traceback
from pathlib import Path

from gui.csv_projects import Project
from gui.run_outputs import OutputInventory, ephys_outputs, miniscope_outputs, multimodal_outputs
from gui.runs import atomic_json


def execute(manifest):
    from aceneurotools.shared.csv_worker import CSVWorker
    from aceneurotools.shared.csv_worker import update_csv_cell

    root = Path(manifest["directory"])
    caiman_temp = root / ".caiman-temp"
    caiman_temp.mkdir(exist_ok=True)
    os.environ.setdefault("CAIMAN_TEMP", str(caiman_temp))
    copies = [(Path(manifest["recording_path"]), root / "recording", manifest["files"])]
    if manifest["kind"] == "multimodal":
        copies.append((Path(manifest["ephys_recording_path"]), root / "recording-ephys", manifest["ephys_files"]))
    for source, destination, files in copies:
        print(f"Preserving {len(files)} recording files in {destination}", flush=True)
        destination.mkdir()
        for item in files:
            origin, target = source / item["path"], destination / item["path"]
            before = origin.stat()
            if before.st_size != item["size"] or before.st_mtime_ns != item["mtime"]:
                raise ValueError(f"Recording file changed since review: {item['path']}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin, target)
            after = origin.stat()
            if after.st_size != before.st_size or after.st_mtime_ns != before.st_mtime_ns:
                raise ValueError(f"Recording file changed during copying: {item['path']}")
    # The original CSV copies remain frozen. Only the execution copies receive run-local paths.
    execution = root / "execution"
    execution.mkdir()
    for name in ["experiments.csv", "analysis_parameters.csv"]:
        shutil.copy2(root / name, execution / name)
    update_csv_cell("recording", manifest["recording_column"], manifest["number"], execution / "experiments.csv")
    if manifest["kind"] == "multimodal":
        update_csv_cell("recording-ephys", "ephys directory", manifest["number"], execution / "experiments.csv")
    params = {
        **manifest["parameters"],
        "line_num": int(manifest["number"]),
        "project_path": str(execution),
        "data_path": str(root),
        "headless": True,
    }
    atomic_json(root / "effective-parameters.json", params)
    report = OutputInventory(root, manifest["kind"], params)
    if manifest["kind"] in {"compute", "miniscope", "preprocess", "multimodal"}:
        # The factory registry intentionally uses explicit imports in this wrapper.
        from aceneurotools.miniscope import onix_miniscope_data_manager, ucla_data_manager  # noqa: F401

        if params.get("crop", True) and params.get("crop_coords"):
            import cv2

            from gui.cropping import validate_coords

            first = next(
                destination / item["path"] for item in manifest["files"] if item["path"].lower().endswith(".avi")
            )
            cap = cv2.VideoCapture(str(first))
            try:
                ok, frame = cap.read()
                if not ok:
                    raise ValueError("The selected AVI could not be decoded.")
                validate_coords(params["crop_coords"], frame.shape[1], frame.shape[0])
            finally:
                cap.release()
    if params.get("crop_coords"):
        staged = Project.open(execution)
        staged.save(
            manifest["number"],
            "parameters",
            {"crop_coords": str(tuple(params["crop_coords"]))},
            staged.digests,
            new_columns=("crop_coords",),
        )
    if manifest["kind"] == "preprocess":
        from aceneurotools.miniscope.miniscope_data_manager import MiniscopeDataManager
        from aceneurotools.miniscope.miniscope_preprocessor import MiniscopePreprocessor

        manager = MiniscopeDataManager.create(
            params["line_num"], project_path=execution, data_path=root, filenames=params["filenames"]
        )
        coords = params.get("crop_coords")
        coords_dict = dict(zip(["x0", "y0", "x1", "y1"], coords)) if coords else None
        preprocessor = MiniscopePreprocessor(manager)
        preprocessor.preprocess_calcium_movie(
            coords_dict=coords_dict,
            **{
                key: value
                for key, value in params.items()
                if key not in {"line_num", "project_path", "data_path", "filenames", "crop_coords"}
            },
        )
        report.artifact("preprocessed_movie", manager.preprocessed_movie_filepath)
        for name in ["max", "std", "min", "mean", "median", "range", "time"]:
            report.array(f"projection_{name}", getattr(manager.projections, name, None), "preprocessing.npz")
        report.array("frame_rate", manager.fr, "preprocessing.npz")
        report.array("time_stamps", manager.time_stamps, "preprocessing.npz")
        report.array("frame_numbers", manager.frame_numbers, "preprocessing.npz")
    elif manifest["kind"] == "compute":
        from aceneurotools.pipelines.compute import ComputePipeline

        if not params.get("crop", True):
            # ComputePipeline checks crop_coords, independently of the crop flag.
            table = execution / "analysis_parameters.csv"
            if "crop_coords" in CSVWorker.csv_row_to_dict(table, params["line_num"]):
                update_csv_cell("", "crop_coords", params["line_num"], table)
        outputs = ComputePipeline().run(
            project_path=execution,
            lab_config=None,
            calcium_signal_dir=root / "calcium_signals",
            data_path=root,
            line_nums=[params["line_num"]],
            headless=True,
            verbose=True,
        )
        if params["line_num"] not in outputs:
            raise RuntimeError("The existing compute pipeline skipped this experiment. Read the run log for its error.")
        report.artifact("mean_fluorescence", outputs[params["line_num"]])
    elif manifest["kind"] == "miniscope":
        from aceneurotools.pipelines.miniscope import MiniscopePipeline

        pipeline = MiniscopePipeline()
        pipeline.run(**params)
        miniscope_outputs(report, pipeline.miniscope_data_manager)
    elif manifest["kind"] == "multimodal":
        from aceneurotools.pipelines.multimodal import MultimodalPipeline

        pipeline = MultimodalPipeline()
        pipeline.run(**params)
        multimodal_outputs(report, pipeline)
    else:
        from aceneurotools.pipelines.ephys import EphysPipeline

        pipeline = EphysPipeline()
        pipeline.run(**params)
        channel = pipeline.ephys_data_manager.get_channel(params["channel_name"])
        ephys_outputs(report, channel)
    report.finish()
    print("Analysis completed. Results and reviewed parameters are preserved in this run folder.", flush=True)


def main():
    path = Path(sys.argv[1])
    try:
        manifest = json.loads(path.read_text())
        execute(manifest)
        atomic_json(path.parent / "outcome.json", {"success": True})
    except Exception as exc:
        traceback.print_exc()
        atomic_json(path.parent / "outcome.json", {"success": False, "error": f"{type(exc).__name__}: {exc}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
