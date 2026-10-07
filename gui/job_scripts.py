"""Export saved experiment settings and the existing worker as a Slurm bundle."""

import base64
import csv
import io
import json
import re
import shlex
import zipfile
from pathlib import Path, PurePosixPath

from gui.csv_projects import ProjectError
from gui.recording_scope import apply_scope
from gui.run_specs import PIPELINES, effective_parameters, validate_settings

ASSETS = Path(__file__).parent
WORKER_FILES = (
    "__init__.py", "cluster_job.py", "run_worker.py", "run_outputs.py", "runs.py",
    "csv_projects.py", "fields.py", "run_specs.py", "cropping.py", "recording_scope.py",
)


def absolute_path(value, label):
    if not isinstance(value, str) or not value.startswith("/") or any(ord(char) < 32 for char in value):
        raise ProjectError(f"{label}: enter an absolute Linux path on the cluster.")
    return value


def positive_integer(value, label):
    if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]*", str(value)):
        raise ProjectError(f"{label}: enter a positive whole number.")
    return int(value)


def generate(project, body):
    number, kind = body["number"], body.get("kind", "compute")
    detail = project.inspect(number)
    if body.get("versions") != detail["versions"]:
        raise ProjectError("Save or reload your experiment before generating scripts.")
    if not number.isascii() or not number.isdigit() or str(int(number)) != number:
        raise ProjectError("Job scripts require an integer experiment number without leading zeros.")
    if detail["parameter_error"] or detail["parameters"] is None:
        raise ProjectError("Add or repair this experiment's analysis settings first.")
    params, _ = effective_parameters(kind, detail["parameters"])
    validate_settings(kind, {key: str(value) for key, value in params.items()})
    options = body.get("cluster")
    if not isinstance(options, dict):
        raise ProjectError("Enter the cluster paths and job resources.")
    source = absolute_path(options.get("recording_path"), "Recording folder")
    ephys_source = absolute_path(options.get("ephys_recording_path"), "Ephys recording folder") if kind == "multimodal" else None
    output = absolute_path(options.get("output_path"), "Output folder")
    if any(PurePosixPath(output).is_relative_to(PurePosixPath(path)) for path in [source, ephys_source] if path):
        raise ProjectError("Choose an output folder outside the recording folders.")
    python = options.get("python", "python")
    if python != "python":
        python = absolute_path(python, "Python interpreter")
    cpus = positive_integer(options.get("cpus"), "CPUs")
    memory = positive_integer(options.get("memory_gb"), "Memory (GB)")
    walltime = options.get("time", "")
    if not isinstance(walltime, str) or not re.fullmatch(r"(?:[0-9]+-)?[0-9]{1,3}:[0-5][0-9]:[0-5][0-9]", walltime):
        raise ProjectError("Time limit: use HH:MM:SS or D-HH:MM:SS.")
    if not any(int(part) for part in re.split(r"[-:]", walltime)):
        raise ProjectError("Time limit must be greater than zero.")
    if "-" in walltime and int(walltime.split("-")[1].split(":")[0]) > 23:
        raise ProjectError("Time limit: hours after the day count must be less than 24.")
    if kind != "ephys":
        coords = params.get("crop_coords")
        if params.get("crop", True) and not coords:
            raise ProjectError("Save a crop first, or set Apply crop to No in Run settings.")
        if coords is not None and (
            not isinstance(coords, (list, tuple)) or len(coords) != 4
            or any(type(v) is not int or v < 0 for v in coords)
            or coords[0] >= coords[2] or coords[1] >= coords[3]
        ):
            raise ProjectError("Crop coordinates must be four ordered, non-negative pixel integers.")
    if kind in {"miniscope", "preprocess", "multimodal"}:
        names_key = "miniscope_filenames" if kind == "multimodal" else "filenames"
        names = params.get(names_key) or []
        if isinstance(names, str):
            names = [names]
        if not isinstance(names, (list, tuple)) or any(
            not isinstance(name, str) or PurePosixPath(name).name != name or "\\" in name
            or name in {"", ".", ".."} for name in names
        ):
            raise ProjectError("Movie filenames must be filenames within the recording, or [] for all movies.")
        params[names_key] = list(names)
        estimate = params.get("save_CNMFE_estimates_filename", "estimates.hdf5")
        if not isinstance(estimate, str) or PurePosixPath(estimate).name != estimate or "\\" in estimate or estimate in {"", ".", ".."}:
            raise ProjectError("Estimates filename must be a filename without a directory path.")
        if kind in {"miniscope", "multimodal"} and params.get("run_CNMFE") and params.get("save_estimates") and not estimate.endswith(".hdf5"):
            raise ProjectError("CNMF-E estimates filenames must end in .hdf5.")
    if kind in {"miniscope", "multimodal"}:
        params.update(n_processes=cpus, parallel=cpus > 1)
    column = "ephys directory" if kind == "ephys" else "calcium imaging directory"
    # Preserve a previously confirmed Box subset without downloading/listing data.
    selected = None
    local = detail["metadata"].get(column, "").strip()
    if local:
        base = body.get("data_path") or str(project.path)
        if not isinstance(base, str):
            raise ProjectError("Invalid local data folder.")
        local_path = Path(base) / local
        if (local_path / ".ace-box.json").exists():
            apply_scope(local_path, [])  # Reuse receipt validation before reading the selection.
            selected = json.loads((local_path / ".ace-box.json").read_text()).get("selection")
    ephys_selected = None
    if kind == "multimodal":
        ephys_local = detail["metadata"].get("ephys directory", "").strip()
        if ephys_local:
            ephys_local_path = Path(body.get("data_path") or str(project.path)) / ephys_local
            if (ephys_local_path / ".ace-box.json").exists():
                apply_scope(ephys_local_path, [])
                ephys_selected = json.loads((ephys_local_path / ".ace-box.json").read_text()).get("selection")
    config = {
        "number": number, "kind": kind, "parameters": params, "cpus": cpus,
        "recording_path": source, "recording_column": column, "output_path": output,
        "selected_files": selected,
        "ephys_recording_path": ephys_source, "ephys_selected_files": ephys_selected,
    }
    name = f"ace-{number}-{kind}"
    directives = [f"#SBATCH --job-name={name}", "#SBATCH --nodes=1", "#SBATCH --ntasks=1",
                  f"#SBATCH --cpus-per-task={cpus}", f"#SBATCH --mem={memory}G",
                  f"#SBATCH --time={walltime}", "#SBATCH --output=slurm-%j.out"]
    for key in ("account", "partition"):
        value = options.get(key, "")
        if not isinstance(value, str) or (value and not re.fullmatch(r"[A-Za-z0-9_.-]+", value)):
            raise ProjectError(f"{key.capitalize()}: use letters, numbers, underscores, dots, or hyphens.")
        if value:
            directives.append(f"#SBATCH --{key}={value}")
    slurm = "\n".join(["#!/bin/bash", *directives, "", "set -euo pipefail",
        'cd "${SLURM_SUBMIT_DIR:?Submit from the extracted job folder}"',
        "export MPLBACKEND=Agg", "export PYTHONUNBUFFERED=1",
        "export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1",
        f"{shlex.quote(python)} run_job.py", ""])
    script = '"""Run this exported experiment without starting the GUI."""\n\nfrom gui.cluster_job import main\n\nif __name__ == "__main__":\n    main()\n'
    files = {"run_job.py": script, "submit.slurm": slurm, "job.json": json.dumps(config, indent=2, allow_nan=False) + "\n"}
    for filename, columns, row in (
        ("experiments.csv", project.metadata_columns, detail["metadata"]),
        ("analysis_parameters.csv", project.parameter_columns, detail["parameters"]),
    ):
        table = io.StringIO(newline="")
        writer = csv.DictWriter(table, fieldnames=columns)
        writer.writeheader()
        writer.writerow(row)
        files[filename] = table.getvalue()
    files["README.txt"] = f"""{PIPELINES[kind]} — experiment {number}

Copy this ZIP to the cluster and extract it. The recording must already be at:
{source}
{f'Electrophysiology recording: {ephys_source}' if ephys_source else ''}
Activate an environment with ACE-NeuroTools (the same version as this GUI), CaImAn,
and its scientific dependencies installed. If your cluster needs module loads,
add those to submit.slurm before its Python command.
From the extracted folder, submit with: sbatch submit.slurm
Alternatively, run: {shlex.quote(python)} run_job.py

job.json contains the saved effective parameters and cluster paths. The selected
experiment's CSV rows and existing GUI worker are bundled; no running GUI is needed.
No recordings or Box credentials are included. Only the exported file selection is
used when a local Box selection receipt exists; otherwise all supported recording
files in the cluster folder are used (subject to the pipeline's movie filenames).

Each run copies recording inputs into a NEW folder under {output}.
Allow disk space for the input copy and results. Original recordings are preserved.
Find the output folder in slurm-<job id>.out. CNMF-E worker processes match the
Slurm CPU allocation; interactive crop/neuron windows are disabled.
Resource values are requests, not measured estimates. Confirm your cluster limits.
Review extracted neurons in the GUI after transferring the results back.
"""
    project.ensure_current()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for filename, content in files.items():
            bundle.writestr(filename, content)
        for filename in WORKER_FILES:
            bundle.writestr(f"gui/{filename}", (ASSETS / filename).read_bytes())
    return {"filename": f"{name}.zip", "archive": base64.b64encode(archive.getvalue()).decode(),
            "script": script, "slurm": slurm, "config": config}
