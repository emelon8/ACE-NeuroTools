"""Import a completed external CNMF-E extraction as an ACE result."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from aceneurotools.gui.csv_projects import ProjectError
from aceneurotools.gui.runs import atomic_json

FORMAT = "ace-cluster-result-v1"


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_bundle(folder, loader=None):
    """Validate a local bundle without modifying it or loading raw movies."""
    if not isinstance(folder, (str, Path)) or not str(folder).strip():
        raise ProjectError("Choose a cluster result folder.")
    folder = Path(folder).expanduser().resolve()
    manifest_path = folder / "manifest.json"
    if not folder.is_dir() or not manifest_path.is_file():
        raise ProjectError("Choose a folder containing manifest.json and CaImAn estimates.")
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, ValueError) as exc:
        raise ProjectError("The cluster manifest is not valid JSON.") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise ProjectError(f"The manifest must declare format {FORMAT}.")
    name = manifest.get("estimates")
    if (
        not isinstance(name, str)
        or Path(name).name != name
        or "\\" in name
        or Path(name).suffix.lower() not in {".hdf5", ".h5"}
    ):
        raise ProjectError("The manifest must name one estimates HDF5 file in the bundle folder.")
    estimates_path = folder / name
    if estimates_path.is_symlink() or not estimates_path.is_file():
        raise ProjectError("The estimates file is missing or is a link.")
    checksum = manifest.get("sha256")
    if not isinstance(checksum, str) or len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum):
        raise ProjectError("The manifest needs a lowercase SHA-256 checksum for the estimates file.")
    if file_sha256(estimates_path) != checksum:
        raise ProjectError("The estimates file does not match the manifest checksum.")
    number = manifest.get("experiment")
    if not isinstance(number, str) or not number.isascii() or not number.isdigit() or str(int(number)) != number:
        raise ProjectError("The manifest needs an experiment number as a canonical string.")
    if not isinstance(manifest.get("parameters"), dict) or not manifest["parameters"]:
        raise ProjectError("The manifest needs the effective extraction parameters.")
    if not isinstance(manifest.get("software"), dict) or not manifest["software"]:
        raise ProjectError("The manifest needs extraction software versions.")
    ids = manifest.get("component_ids")
    if not isinstance(ids, list) or not ids or any(type(value) is not int or value < 0 for value in ids) or len(ids) != len(set(ids)):
        raise ProjectError("The manifest needs unique, non-negative original component IDs.")
    frame_rate = manifest.get("frame_rate")
    if isinstance(frame_rate, bool) or not isinstance(frame_rate, (int, float)) or not math.isfinite(frame_rate) or frame_rate <= 0:
        raise ProjectError("The manifest needs a positive frame rate in Hz.")
    if loader is None:
        from aceneurotools.gui.neurons import load_estimates

        loader = load_estimates
    try:
        obj = loader(estimates_path)
        dims = tuple(int(value) for value in obj.dims)
        footprints, traces = obj.estimates.A, np.asarray(obj.estimates.C)
        footprint_values = footprints.data if hasattr(footprints, "data") else np.asarray(footprints)
        if (
            len(dims) != 2
            or min(dims) <= 0
            or footprints.shape != (math.prod(dims), len(ids))
            or traces.ndim != 2
            or traces.shape[0] != len(ids)
            or traces.shape[1] == 0
            or not np.isfinite(traces).all()
            or not np.isfinite(footprint_values).all()
        ):
            raise ValueError("Inconsistent footprints, traces, or component IDs")
        saved_rate = float(obj.params.get("data", "fr"))
        if not math.isclose(saved_rate, float(frame_rate), rel_tol=1e-6):
            raise ValueError("Frame rate differs from the estimates")
    except Exception as exc:
        raise ProjectError(f"The CaImAn estimates do not match this manifest: {exc}") from exc
    return manifest, estimates_path


def import_bundle(project, folder, loader=None):
    manifest, source = read_bundle(folder, loader=loader)
    number = manifest["experiment"]
    project.inspect(number)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    root = project.path / ".ace-runs"
    root.mkdir(exist_ok=True)
    destination = root / run_id
    with tempfile.TemporaryDirectory(prefix=".cluster-import-", dir=root) as temporary:
        stage = Path(temporary)
        copied = stage / manifest["estimates"]
        shutil.copyfile(source, copied)
        if file_sha256(copied) != manifest["sha256"]:
            raise ProjectError("The estimates changed while copying. Import was cancelled.")
        atomic_json(stage / "manifest.json", manifest)
        atomic_json(stage / "effective-parameters.json", manifest["parameters"])
        (stage / "run.log").write_text("Imported cluster extraction; no local extraction was run.\n")
        from aceneurotools.gui.run_outputs import OutputInventory

        report = OutputInventory(stage, "miniscope", manifest["parameters"])
        report.artifact("neuron_estimates", copied)
        report.artifact("cluster_manifest", stage / "manifest.json")
        report.array("neuron_ids", np.asarray(manifest["component_ids"], dtype=int))
        report.missing("ca_events_idx", reason="Run postprocessing or curate neurons to detect local events")
        report.diagnostics.update(
            origin="cluster-import",
            source_sha256=manifest["sha256"],
            neuron_count=len(manifest["component_ids"]),
            frame_rate=manifest["frame_rate"],
        )
        report.finish()
        now = datetime.now(timezone.utc).isoformat()
        atomic_json(
            stage / "run.json",
            {
                "id": run_id,
                "number": number,
                "kind": "miniscope",
                "label": "Imported cluster CNMF-E",
                "state": "completed",
                "started": now,
                "finished": now,
                "parameters": manifest["parameters"],
                "origin": "cluster-import",
                "source_sha256": manifest["sha256"],
            },
        )
        stage.rename(destination)
    return run_id
