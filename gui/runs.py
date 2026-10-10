"""Reviewed, isolated subprocess runs of the unchanged analysis pipelines."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from gui.csv_projects import ProjectError
from gui.recording_scope import apply_scope
from gui.run_specs import PIPELINES, effective_parameters

ROOT = Path(__file__).parent.parent
IGNORED = {"saved_movies", ".ace-runs", ".ace-gui-backups", "__pycache__"}
RAW_SUFFIXES = {
    ".avi",
    ".json",
    ".csv",
    ".raw",
    ".ncs",
    ".nev",
    ".nse",
    ".ntt",
    ".rhs",
    ".rhd",
    ".dat",
    ".bin",
    ".xml",
    ".txt",
}


def recording_path(project, metadata, data_path, column):
    value = metadata.get(column, "").strip()
    if not value:
        raise ProjectError(f"Set the {column} in Experiment details first.")
    if ";" in value:
        raise ProjectError(
            f"{column} contains multiple folders. The current pipeline needs one recording folder per run."
        )
    path = (Path(data_path).expanduser() / value).resolve()
    if not path.is_dir():
        raise ProjectError(
            f"Recording folder is unavailable on this computer: {path}. Choose its local folder in Experiment details, or choose the base folder that contains this relative location."
        )
    return path


def inventory(path):
    files = []
    for folder, directories, names in os.walk(path):
        directories[:] = sorted(name for name in directories if name not in IGNORED and not name.startswith("."))
        for name in sorted(names):
            item = Path(folder) / name
            if item.suffix.lower() in RAW_SUFFIXES and not name.startswith("."):
                info = item.stat()
                files.append({"path": str(item.relative_to(path)), "size": info.st_size, "mtime": info.st_mtime_ns})
    return files


def atomic_json(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False))
    os.replace(temp, path)


class Runs:
    def __init__(self):
        self.lock = threading.RLock()
        self.reviews = {}
        self.processes = {}

    def review(self, project, body):
        number, kind = body.get("number"), body.get("kind", "compute")
        detail = project.inspect(number)
        if body.get("versions") != detail["versions"]:
            raise ProjectError("Save or reload your experiment before reviewing a run.")
        if not isinstance(kind, str) or kind not in PIPELINES:
            raise ProjectError("Choose an analysis from the run menu.")
        if not isinstance(number, str) or not number.isascii() or not number.isdigit() or str(int(number)) != number:
            raise ProjectError(
                "The existing pipelines require a non-negative integer experiment number without leading zeros. This record can still be edited."
            )
        if detail["parameter_error"] or detail["parameters"] is None:
            raise ProjectError("Add or repair analysis settings for this experiment before running.")
        params, sources = effective_parameters(kind, detail["parameters"])
        blockers = []
        try:
            from gui.run_specs import validate_settings

            validate_settings(
                kind,
                {
                    key: str(value) if not isinstance(value, (list, tuple)) else json.dumps(value)
                    for key, value in params.items()
                },
            )
        except ValueError as exc:
            blockers.append(str(exc))
        column = "ephys directory" if kind == "ephys" else "calcium imaging directory"
        base = body.get("data_path") or str(project.path)
        if not isinstance(base, str):
            raise ProjectError("Choose a local data base folder.")
        records, raw = [], None
        ephys_records, ephys_raw = [], None
        try:
            raw = recording_path(project, detail["metadata"], base, column)
            records = apply_scope(raw, inventory(raw))
            if not records:
                blockers.append("No supported recording files were found in this folder.")
            if kind != "ephys" and not any(item["path"].lower().endswith(".avi") for item in records):
                blockers.append("No AVI movies were found in this recording folder.")
        except ProjectError as exc:
            blockers.append(str(exc))
        if kind == "multimodal":
            try:
                ephys_raw = recording_path(project, detail["metadata"], base, "ephys directory")
                ephys_records = apply_scope(ephys_raw, inventory(ephys_raw))
                if not any(
                    Path(item["path"]).suffix.lower() in {".ncs", ".rhs", ".rhd", ".dat", ".bin", ".raw"}
                    for item in ephys_records
                ):
                    blockers.append("No electrophysiology recording files were found in the ephys folder.")
            except ProjectError as exc:
                blockers.append(str(exc))
        if kind != "ephys":
            coords = params.get("crop_coords")
            if params.get("crop", True) and not coords:
                blockers.append(
                    "Choose and save a crop first, or save Apply crop = No in Run settings to run the full frame."
                )
            if coords is not None and (
                not isinstance(coords, (list, tuple))
                or len(coords) != 4
                or any(type(v) is not int or v < 0 for v in coords)
                or coords[0] >= coords[2]
                or coords[1] >= coords[3]
            ):
                blockers.append("Crop coordinates must be four ordered, non-negative pixel integers.")
        if kind in {"miniscope", "preprocess", "multimodal"}:
            names_key = "miniscope_filenames" if kind == "multimodal" else "filenames"
            names = params.get(names_key, [])
            if isinstance(names, str):
                names = [names]
                params[names_key] = names
            if names is None:
                params[names_key] = names = []
            if not isinstance(names, list) or any(
                not isinstance(name, str) or Path(name).name != name or "\\" in name for name in names
            ):
                blockers.append(
                    "Movie filenames must be basenames within this recording, or an empty list for all movies."
                )
            elif records and any(not any(Path(item["path"]).name == name for item in records) for name in names):
                blockers.append(
                    "One or more selected movie filenames are missing. Edit filenames in Run settings; [] selects all movies."
                )
            estimate = params.get("save_CNMFE_estimates_filename", "estimates.hdf5")
            if (
                not isinstance(estimate, str)
                or Path(estimate).name != estimate
                or "\\" in estimate
                or estimate in {"", ".", ".."}
            ):
                blockers.append("The estimates filename must be a filename, without a directory path.")
            elif (
                kind in {"miniscope", "multimodal"}
                and params.get("run_CNMFE")
                and params.get("save_estimates")
                and not estimate.endswith(".hdf5")
            ):
                blockers.append(
                    "CNMF-E estimates filenames must end in .hdf5 for the installed CaImAn save method. Curated copies can be renamed separately."
                )
        if raw and kind != "ephys":
            import cv2

            from gui.cropping import validate_coords

            sizes = set()
            for item in records:
                if not item["path"].lower().endswith(".avi"):
                    continue
                if (
                    kind in {"miniscope", "preprocess", "multimodal"}
                    and params.get("miniscope_filenames" if kind == "multimodal" else "filenames")
                    and Path(item["path"]).name
                    not in params["miniscope_filenames" if kind == "multimodal" else "filenames"]
                ):
                    continue
                cap = cv2.VideoCapture(str(raw / item["path"]))
                try:
                    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    if not cap.isOpened() or width <= 0 or height <= 0:
                        blockers.append(f"Movie cannot be opened: {item['path']}. Check the recording download.")
                    else:
                        sizes.add((width, height))
                        if params.get("crop", True) and params.get("crop_coords"):
                            try:
                                validate_coords(params["crop_coords"], width, height)
                            except ProjectError as exc:
                                blockers.append(f"{item['path']}: {exc}")
                finally:
                    cap.release()
            if len(sizes) > 1:
                blockers.append(
                    "The selected movies have different image dimensions. Choose a consistent recording or movie subset before running."
                )
        root = project.path / ".ace-runs"
        if any(root.is_relative_to(path) or path.is_relative_to(root) for path in [raw, ephys_raw] if path):
            blockers.append(
                "Recording folders must be outside this project's .ace-runs result folder. Open the folder containing this project's CSVs."
            )
        size = sum(item["size"] for item in [*records, *ephys_records])
        if shutil.disk_usage(project.path).free < size:
            blockers.append("Not enough free disk space to preserve a private copy of this recording for the run.")
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        directory = root / run_id
        destinations = {
            "Run folder": str(directory),
            "Reviewed parameters": str(directory / "effective-parameters.json"),
            "Run log": str(directory / "run.log"),
            "Output inventory": str(directory / "output-inventory.json"),
            "Diagnostics summary": str(directory / "diagnostics.json"),
        }
        if kind in {"miniscope", "multimodal"}:
            destinations["Signals, component IDs, and postprocessing"] = str(directory / "postprocessing.npz")
            destinations["Spatial footprints (when extracted)"] = str(directory / "components.npz")
            if params.get("find_calcium_events"):
                destinations["Calcium events (when estimates are available)"] = str(directory / "calcium-events.json")
            destinations["Quality diagnostics (when available)"] = str(directory / "diagnostics.npz")
            if params.get("run_CNMFE") and params.get("save_estimates"):
                destinations["Neuron estimates"] = str(
                    directory
                    / "recording"
                    / "saved_movies"
                    / str(params.get("save_CNMFE_estimates_filename", "estimates.hdf5"))
                )
            if params.get("save_CNMFE_params"):
                destinations["CaImAn parameters"] = str(directory / "recording" / "saved_movies" / "opts_caiman.json")
        if kind == "multimodal":
            destinations["Electrophysiology data"] = str(directory / "ephys.npz")
            destinations["Electrophysiology events"] = str(directory / "ephys-events.json")
            destinations["Aligned timing and phases"] = str(directory / "alignment.npz")
            destinations["Event alignment (when requested)"] = str(directory / "ephys_idx_ca_events.json")
        elif kind == "compute":
            destinations["Mean fluorescence"] = str(directory / "calcium_signals" / f"meanFluorescence_{number}.npz")
        elif kind == "preprocess":
            destinations["Preprocessed movies"] = str(directory / "recording" / "saved_movies")
            destinations["Projection and timing arrays"] = str(directory / "preprocessing.npz")
        elif kind == "ephys":
            destinations["Electrophysiology data"] = str(directory / "ephys.npz")
            destinations["Electrophysiology events"] = str(directory / "ephys-events.json")
        value = {
            "number": number,
            "project": project.id,
            "project_path": str(project.path),
            "kind": kind,
            "label": PIPELINES[kind],
            "metadata": detail["metadata"],
            "settings": detail["parameters"],
            "parameters": params,
            "parameter_sources": sources,
            "versions": detail["versions"],
            "data_path": base,
            "recording_path": str(raw) if raw else "",
            "recording_column": column,
            "files": records,
            "ephys_recording_path": str(ephys_raw) if ephys_raw else "",
            "ephys_files": ephys_records,
            "input_bytes": size,
            "output_root": str(root),
            "run_id": run_id,
            "directory": str(directory),
            "destinations": destinations,
            "blockers": blockers,
        }
        token = uuid.uuid4().hex
        with self.lock:
            self.reviews = {
                key: review for key, review in self.reviews.items() if time.monotonic() - review["time"] < 1800
            }
            self.reviews[token] = {"value": value, "time": time.monotonic()}
        return {**value, "review": token}

    def start(self, project, body):
        if body.get("confirmed") is not True:
            raise ProjectError("Review the experiment details and parameters, then confirm before starting.")
        token = body.get("review")
        with self.lock:
            reviewed = self.reviews.get(token) if isinstance(token, str) else None
            if not reviewed or time.monotonic() - reviewed["time"] >= 1800:
                raise ProjectError("This review expired. Review the experiment again before running.")
            value = reviewed["value"]
            if value["project"] != project.id or (body.get("number") is not None and body["number"] != value["number"]):
                raise ProjectError("Review the selected project's experiment first.")
            if value["blockers"]:
                raise ProjectError("Resolve the problems listed in the review before running.")
            project.ensure_current()
            if value["versions"] != project.digests:
                raise ProjectError("Parameters changed after review. Review them again before running.")
            if apply_scope(Path(value["recording_path"]), inventory(Path(value["recording_path"]))) != value["files"]:
                raise ProjectError("Recording files changed after review. Review the experiment again.")
            if (
                value["kind"] == "multimodal"
                and apply_scope(Path(value["ephys_recording_path"]), inventory(Path(value["ephys_recording_path"])))
                != value["ephys_files"]
            ):
                raise ProjectError("Electrophysiology files changed after review. Review the experiment again.")
            if any(process.poll() is None for process in self.processes.values()):
                raise ProjectError(
                    "An analysis is already running. Wait for it to finish or stop it before starting another."
                )
            run_id = value["run_id"]
            directory = Path(value["directory"])
            directory.mkdir(parents=True)
            for name in ["experiments.csv", "analysis_parameters.csv"]:
                shutil.copy2(project.path / name, directory / name)
            project.ensure_current()
            value = {
                **value,
                "id": run_id,
                "directory": str(directory),
                "state": "running",
                "started": datetime.now(timezone.utc).isoformat(),
                "finished": None,
            }
            atomic_json(directory / "run.json", value)
            env = {
                **os.environ,
                "PYTHONPATH": os.pathsep.join([str(ROOT), str(ROOT / "src")]),
                "MPLBACKEND": "Agg",
                "MPLCONFIGDIR": str(directory / ".matplotlib"),
                "PYTHONUNBUFFERED": "1",
            }
            with (directory / "run.log").open("wb") as log:
                try:
                    process = subprocess.Popen(
                        [sys.executable, "-m", "gui.run_worker", str(directory / "run.json")],
                        cwd=directory,
                        env=env,
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                except OSError as exc:
                    value["state"], value["error"] = "failed", f"Could not launch analysis: {exc.strerror}"
                    atomic_json(directory / "run.json", value)
                    raise ProjectError(value["error"]) from None
            self.processes[str(directory)] = process
            self.reviews.pop(token, None)
            threading.Thread(target=self._watch, args=(process, directory), daemon=True).start()
        return self.inspect(project, run_id)

    def _watch(self, process, directory):
        code = process.wait()
        with self.lock:
            value = json.loads((directory / "run.json").read_text())
            if value["state"] == "running":
                value["state"] = "completed" if code == 0 else "failed"
                value["exit_code"] = code
                value["finished"] = datetime.now(timezone.utc).isoformat()
                outcome = directory / "outcome.json"
                if outcome.exists():
                    result = json.loads(outcome.read_text())
                    if result.get("error"):
                        value["error"] = result["error"]
                atomic_json(directory / "run.json", value)

    def directory(self, project, run_id):
        if not isinstance(run_id, str) or not __import__("re").fullmatch(r"[0-9]{8}T[0-9]{6}-[a-f0-9]{8}", run_id):
            raise ProjectError("Choose a saved run from Results.")
        directory = project.path / ".ace-runs" / run_id
        if not (directory / "run.json").is_file():
            raise ProjectError("This run could not be found.")
        return directory

    def _resolve(self, directory, value):
        """Settle a recorded running state that this server is not running; the caller holds the lock."""
        if value["state"] == "running" and str(directory) not in self.processes:
            outcome = directory / "outcome.json"
            if outcome.is_file():
                result = json.loads(outcome.read_text())
                value["state"] = "completed" if result.get("success") else "failed"
                value["error"] = result.get("error")
                value["finished"] = datetime.fromtimestamp(outcome.stat().st_mtime, timezone.utc).isoformat()
                atomic_json(directory / "run.json", value)
            else:
                value["state"] = "untracked"
        return value

    def inspect(self, project, run_id):
        directory = self.directory(project, run_id)
        with self.lock:
            value = self._resolve(directory, json.loads((directory / "run.json").read_text()))
            outputs = []
            for item in sorted(directory.rglob("*")):
                rel = item.relative_to(directory)
                if (
                    item.is_file()
                    and not any(part.startswith(".") for part in rel.parts)
                    and (rel.parts[0] not in {"recording", "recording-ephys"} or "saved_movies" in rel.parts)
                ):
                    outputs.append({"name": str(rel), "size": item.stat().st_size})
            log = directory / "run.log"
            inventory_path = directory / "output-inventory.json"
            output_inventory = json.loads(inventory_path.read_text()) if inventory_path.is_file() else None
            with log.open("rb") if log.exists() else open(os.devnull, "rb") as handle:
                handle.seek(0, 2)
                handle.seek(max(0, handle.tell() - 65536))
                tail = handle.read().decode("utf-8", errors="replace")
            return {
                "id": value["id"],
                "number": value["number"],
                "kind": value["kind"],
                "label": value["label"],
                "state": value["state"],
                "started": value["started"],
                "finished": value["finished"],
                "directory": str(directory),
                "files": outputs,
                "output_inventory": output_inventory,
                "log": tail,
                "parameters": value["parameters"],
                "error": value.get("error"),
                "exit_code": value.get("exit_code"),
            }

    def listing(self, project, number):
        root = project.path / ".ace-runs"
        items = []
        if root.is_dir():
            for path in sorted(root.glob("*/run.json"), reverse=True):
                try:
                    value = json.loads(path.read_text())
                    if value["number"] == number:
                        items.append(self.inspect(project, path.parent.name))
                except (ValueError, KeyError, OSError):
                    continue
        return {"runs": items}

    def stop(self, project, run_id):
        import signal

        directory = self.directory(project, run_id)
        with self.lock:
            process = self.processes.get(str(directory))
            if not process or process.poll() is not None:
                raise ProjectError("This run is no longer active in this server session.")
            os.killpg(process.pid, signal.SIGTERM)
            value = json.loads((directory / "run.json").read_text())
            value["state"], value["finished"] = "stopped", datetime.now(timezone.utc).isoformat()
            atomic_json(directory / "run.json", value)
        return self.inspect(project, run_id)
