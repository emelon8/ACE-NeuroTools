"""Portable entry point packaged with the existing GUI analysis worker."""

import json
import os
import shutil
import traceback
import uuid
from pathlib import Path

os.environ["MPLBACKEND"] = "Agg"

from gui.run_worker import execute
from gui.runs import atomic_json, inventory


def main():
    bundle = Path(__file__).resolve().parents[1]
    config = json.loads((bundle / "job.json").read_text())
    source = Path(config["recording_path"])
    if not source.is_dir():
        raise ValueError(f"Cluster recording folder does not exist: {source}")
    if Path(config["output_path"]).resolve().is_relative_to(source.resolve()):
        raise ValueError("Choose an output folder outside the recording folder.")
    files = inventory(source)
    if config["selected_files"] is not None:
        available = {item["path"] for item in files}
        missing = set(config["selected_files"]) - available
        if missing:
            raise ValueError(f"Selected recording files are missing on the cluster: {sorted(missing)}")
        files = [item for item in files if item["path"] in config["selected_files"]]
    if not files or (config["kind"] != "ephys" and not any(item["path"].lower().endswith(".avi") for item in files)):
        raise ValueError("No supported recording files were found for this analysis.")
    ephys_files = []
    if config["kind"] == "multimodal":
        ephys_source = Path(config["ephys_recording_path"])
        if not ephys_source.is_dir():
            raise ValueError(f"Cluster ephys recording folder does not exist: {ephys_source}")
        if Path(config["output_path"]).resolve().is_relative_to(ephys_source.resolve()):
            raise ValueError("Choose an output folder outside the ephys recording folder.")
        ephys_files = inventory(ephys_source)
        if config["ephys_selected_files"] is not None:
            available = {item["path"] for item in ephys_files}
            missing = set(config["ephys_selected_files"]) - available
            if missing:
                raise ValueError(f"Selected ephys files are missing on the cluster: {sorted(missing)}")
            ephys_files = [item for item in ephys_files if item["path"] in config["ephys_selected_files"]]
        if not any(
            Path(item["path"]).suffix.lower() in {".ncs", ".rhs", ".rhd", ".dat", ".bin", ".raw"}
            for item in ephys_files
        ):
            raise ValueError("No electrophysiology recording files were found for this analysis.")
    params = config["parameters"]
    if config["kind"] in {"miniscope", "preprocess", "multimodal"}:
        names_key = "miniscope_filenames" if config["kind"] == "multimodal" else "filenames"
        missing = set(params.get(names_key, [])) - {Path(item["path"]).name for item in files}
        if missing:
            raise ValueError(f"Selected movie filenames are missing on the cluster: {sorted(missing)}")
    if config["kind"] in {"miniscope", "multimodal"}:
        cpus = int(os.environ.get("SLURM_CPUS_PER_TASK", config["cpus"]))
        if cpus < 1:
            raise ValueError("The CPU allocation must be positive.")
        params.update(n_processes=cpus, parallel=cpus > 1)
    # Every submission, including resubmissions and direct Python runs, is isolated.
    root = Path(config["output_path"]) / f"ace-{config['number']}-{uuid.uuid4().hex[:12]}"
    root.mkdir(parents=True)
    manifest = {**config, "directory": str(root), "files": files, "ephys_files": ephys_files, "parameters": params}
    for name in ("experiments.csv", "analysis_parameters.csv"):
        shutil.copy2(bundle / name, root / name)
    atomic_json(root / "manifest.json", manifest)
    print(f"Job outputs: {root}", flush=True)
    try:
        execute(manifest)
    except Exception as exc:
        traceback.print_exc()
        atomic_json(root / "outcome.json", {"success": False, "error": f"{type(exc).__name__}: {exc}"})
        raise
    atomic_json(root / "outcome.json", {"success": True})


if __name__ == "__main__":
    main()
