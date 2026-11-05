"""Portable description of reviewed analysis runs, and the commands that reproduce them.

A *run plan* is the shared input for every feature that starts or exports work:
single runs, batch queues, the Output script view and supercomputer bundles. It is
built only from reviewed runs (``Runs.review``), so every entry has already passed
the GUI's input and settings checks.

The plan records what the CSVs say, not where this computer keeps the recordings:
``recordings`` holds the experiment's recording columns exactly as saved in
experiments.csv. Exporters decide how those resolve on another machine.

Commands come in two forms:

``cli``
    The existing per-experiment command-line entry point. It reads settings from
    analysis_parameters.csv, so it reproduces the run when given the same CSVs.
    ``None`` when no command-line entry point exists for that analysis; ``cli_note``
    then says why.
``python``
    A Python snippet that calls the same public API the GUI worker calls, with the
    reviewed effective settings written out explicitly.

This module never imports the pipelines or CaImAn; it only needs the shared
option-name table, so building plans and commands stays fast.
"""

from __future__ import annotations

import json
import pprint
import shlex
import subprocess
from datetime import datetime, timezone
from typing import Any

from aceneurotools.shared.calcium_imaging_names import LEGACY_OPTIONS

SCHEMA = "ace-run-plan/1"
KINDS = ("compute", "preprocess", "miniscope", "ephys", "multimodal")
EXECUTION_MODES = ("sequential", "parallel")

# Recording columns each analysis reads from experiments.csv.
RECORDING_COLUMNS = {
    "compute": ("calcium imaging directory",),
    "preprocess": ("calcium imaging directory",),
    "miniscope": ("calcium imaging directory",),
    "ephys": ("ephys directory",),
    "multimodal": ("calcium imaging directory", "ephys directory"),
}

# Per-experiment command-line modules, as documented in the pipeline guides.
CLI_MODULES = {
    "miniscope": "aceneurotools.pipelines.calcium_imaging",
    "ephys": "aceneurotools.pipelines.ephys",
    "multimodal": "aceneurotools.pipelines.multimodal",
}
NO_CLI = {
    "compute": (
        "The mean-fluorescence command (python -m aceneurotools.pipelines.compute) requires "
        "--lab-config and --calcium-signal-dir. The GUI runs it without a lab_config.json, "
        "so use the Python form below."
    ),
    "preprocess": "Crop and preprocess has no command-line entry point. Use the Python form below.",
}
PIPELINE_CLASSES = {
    "miniscope": ("aceneurotools.pipelines.calcium_imaging", "CalciumImagingPipeline"),
    "ephys": ("aceneurotools.pipelines.ephys", "EphysPipeline"),
    "multimodal": ("aceneurotools.pipelines.multimodal", "MultimodalPipeline"),
}
# Keys the worker passes separately from the reviewed settings.
_RUN_KEYS = {"line_num", "project_path", "data_path", "headless"}
# Settings gui.run_worker gives the preprocessor as separate arguments, not as **options.
PREPROCESS_SEPARATE = {"filenames", "crop_coords"}


def entry_from_review(review: dict[str, Any]) -> dict[str, Any]:
    """Return the portable part of a reviewed run (``Runs.review`` output)."""
    kind = review["kind"]
    if kind not in KINDS:
        raise ValueError(f"Unsupported analysis: {kind}")
    metadata = review.get("metadata") or {}
    return {
        "number": review["number"],
        "kind": kind,
        "label": review["label"],
        "parameters": review["parameters"],
        "parameter_sources": review["parameter_sources"],
        "recordings": {column: metadata.get(column, "") for column in RECORDING_COLUMNS[kind]},
        "files": review.get("files", []),
        "ephys_files": review.get("ephys_files", []),
        "input_bytes": review.get("input_bytes", 0),
        "blockers": list(review.get("blockers", [])),
    }


def new_plan(
    *,
    project_id: str,
    project_path: str,
    versions: dict[str, str | None],
    entries: list[dict[str, Any]],
    mode: str = "sequential",
    max_concurrent: int = 1,
) -> dict[str, Any]:
    plan = {
        "schema": SCHEMA,
        "created": datetime.now(timezone.utc).isoformat(),
        "project": {"id": project_id, "path": project_path, "versions": dict(versions)},
        "execution": {"mode": mode, "max_concurrent": max_concurrent},
        "entries": list(entries),
    }
    validate_plan(plan)
    return plan


def validate_plan(plan: Any) -> None:
    """Raise ``ValueError`` with a user-facing message if ``plan`` is malformed."""
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA:
        raise ValueError(f"This is not an {SCHEMA} run plan.")
    project = plan.get("project")
    if not isinstance(project, dict) or not isinstance(project.get("path"), str):
        raise ValueError("The run plan does not name its project.")
    execution = plan.get("execution")
    if not isinstance(execution, dict) or execution.get("mode") not in EXECUTION_MODES:
        raise ValueError("Choose sequential or parallel execution.")
    limit = execution.get("max_concurrent")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("The number of concurrent runs must be a whole number of at least 1.")
    if execution["mode"] == "sequential" and limit != 1:
        raise ValueError("Sequential execution runs one analysis at a time.")
    entries = plan.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Choose at least one experiment to run.")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("kind") not in KINDS:
            raise ValueError("Each run needs a supported analysis.")
        number = entry.get("number")
        if not isinstance(number, str) or not number.isascii() or not number.isdigit() or str(int(number)) != number:
            raise ValueError(f"Experiment numbers must be non-negative integers: {number!r}")
        if (number, entry["kind"]) in seen:
            raise ValueError(f"Experiment {number} is listed twice for {entry.get('label', entry['kind'])}.")
        seen.add((number, entry["kind"]))
        if not isinstance(entry.get("parameters"), dict):
            raise ValueError(f"Experiment {number} has no reviewed settings.")


def blockers(plan: dict[str, Any]) -> list[str]:
    """Every unresolved review problem in the plan, labelled with its experiment."""
    return [
        f"Experiment {entry['number']} ({entry['label']}): {problem}"
        for entry in plan["entries"]
        for problem in entry.get("blockers", [])
    ]


def canonical_options(parameters: dict[str, Any]) -> dict[str, Any]:
    """Rename historical option spellings to the names the pipeline APIs declare."""
    return {LEGACY_OPTIONS.get(key, key): value for key, value in parameters.items() if key not in _RUN_KEYS}


def cli_argv(entry: dict[str, Any], *, project_path: str, data_path: str | None, python: str = "python") -> list[str] | None:
    """Arguments for the per-experiment command, or ``None`` when there is none."""
    module = CLI_MODULES.get(entry["kind"])
    if module is None:
        return None
    argv = [python, "-m", module, "--line-num", entry["number"], "--project-path", project_path]
    if data_path:
        argv += ["--data-path", data_path]
    return [*argv, "--headless"]


def python_snippet(entry: dict[str, Any], *, project_path: str, data_path: str | None) -> str:
    """A runnable Python snippet that makes the same API call as the GUI worker."""
    kind, number = entry["kind"], int(entry["number"])
    options = canonical_options(entry["parameters"])
    paths = {"project_path": project_path, "data_path": data_path}
    if kind in PIPELINE_CLASSES:
        module, cls = PIPELINE_CLASSES[kind]
        call = {"line_num": number, **paths, **options, "headless": True}
        return "\n".join(
            [
                f"from {module} import {cls}",
                "",
                f"pipeline = {cls}()",
                f"pipeline.run(**{_literal(call)})",
                "",
            ]
        )
    if kind == "compute":
        return "\n".join(
            [
                "from pathlib import Path",
                "",
                "from aceneurotools.pipelines.compute import ComputePipeline",
                "",
                "outputs = ComputePipeline().run(",
                f"    project_path={project_path!r},",
                "    lab_config=None,",
                f"    calcium_signal_dir=Path({project_path!r}) / 'calcium_signals',",
                f"    data_path={data_path!r},",
                f"    line_nums=[{number}],",
                "    headless=True,",
                "    verbose=True,",
                ")",
                "",
            ]
        )
    # preprocess: the same calls as gui.run_worker, which has no pipeline class to call.
    # The worker passes settings to the preprocessor without renaming them; so does this.
    settings = {key: value for key, value in entry["parameters"].items() if key not in _RUN_KEYS}
    coords = settings.get("crop_coords")
    rest = {**{key: value for key, value in settings.items() if key not in PREPROCESS_SEPARATE}, "headless": True}
    coords_dict = dict(zip(["x0", "y0", "x1", "y1"], coords)) if coords else None
    return "\n".join(
        [
            "# Importing the acquisition readers registers them with the data-manager factory.",
            "from aceneurotools.miniscope import onix_miniscope_data_manager, ucla_data_manager  # noqa: F401",
            "from aceneurotools.calcium_imaging.calcium_imaging_data_manager import CalciumImagingDataManager",
            "from aceneurotools.calcium_imaging.calcium_imaging_preprocessor import CalciumImagingPreprocessor",
            "",
            "manager = CalciumImagingDataManager.create(",
            f"    {number},",
            f"    project_path={project_path!r},",
            f"    data_path={data_path!r},",
            f"    filenames={_literal(settings.get('filenames', []))},",
            ")",
            "CalciumImagingPreprocessor(manager).preprocess_calcium_movie(",
            f"    coords_dict={_literal(coords_dict)},",
            f"    **{_literal(rest)},",
            ")",
            "",
        ]
    )


def invocation(
    entry: dict[str, Any], *, project_path: str, data_path: str | None, python: str = "python"
) -> dict[str, Any]:
    """Both reproducible forms of one plan entry, with shell renderings of the command."""
    argv = cli_argv(entry, project_path=project_path, data_path=data_path, python=python)
    return {
        "number": entry["number"],
        "kind": entry["kind"],
        "label": entry["label"],
        "cli": argv,
        "cli_posix": shlex.join(argv) if argv else None,
        "cli_windows": subprocess.list2cmdline(argv) if argv else None,
        "cli_note": NO_CLI.get(entry["kind"]),
        "python": python_snippet(entry, project_path=project_path, data_path=data_path),
    }


def _literal(value: Any) -> str:
    """Python source for a JSON-compatible value (``true`` -> ``True``, ``null`` -> ``None``)."""
    # Round-trip through JSON first so only plain lists/dicts/strings/numbers remain.
    return pprint.pformat(json.loads(json.dumps(value, allow_nan=False)), sort_dicts=False, width=100)
