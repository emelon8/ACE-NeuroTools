"""Helpers for consistent pipeline CLI parameter handling."""

from __future__ import annotations

import inspect
import warnings
from pathlib import Path
from typing import Any, Callable

from aceneurotools.shared.exceptions import ConfigurationError


def run_allowed_keys(run_callable: Callable[..., Any]) -> set[str]:
    """Return accepted kwargs for a pipeline run() method."""
    return {
        name
        for name, param in inspect.signature(run_callable).parameters.items()
        if name != "self" and param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }


def build_run_params(
    *,
    defaults: dict[str, Any],
    allowed_keys: set[str],
    line_num: int,
    project_path: str,
    data_path: str | None,
    headless: bool,
    csv_loader: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    """Build run params with canonical precedence: defaults -> CSV -> CLI."""
    params = dict(defaults)
    params["line_num"] = line_num

    try:
        csv_params = csv_loader(line_num, project_path=Path(project_path))
    except FileNotFoundError as e:
        warnings.warn(str(e), stacklevel=2)
        csv_params = {}

    for key, value in csv_params.items():
        if key in allowed_keys:
            params[key] = value
        else:
            warnings.warn(f"Ignoring unknown analysis_parameters key: {key}", stacklevel=2)

    params["project_path"] = project_path
    if data_path:
        params["data_path"] = data_path
    params["headless"] = bool(headless)
    return params


def validate_common_inputs(*, line_num: Any, project_path: Any, data_path: Any = None) -> None:
    """Validate required common CLI inputs before pipeline execution."""
    if not isinstance(line_num, int) or line_num < 0:
        raise ConfigurationError(
            "line_num must be a non-negative integer.",
            stage="validate_cli_inputs",
            hint="Pass --line-num with a valid experiment row number.",
        )
    if not isinstance(project_path, (str, Path)) or not str(project_path).strip():
        raise ConfigurationError(
            "project_path must be a non-empty path.",
            stage="validate_cli_inputs",
            hint="Pass --project-path to the directory containing experiments.csv.",
        )
    project = Path(project_path)
    if not project.exists() or not project.is_dir():
        raise ConfigurationError(
            f"project_path does not exist or is not a directory: {project}",
            stage="validate_cli_inputs",
            hint="Check --project-path and ensure it points to your project directory.",
        )
    if data_path is not None:
        if not isinstance(data_path, (str, Path)) or not str(data_path).strip():
            raise ConfigurationError(
                "data_path must be a non-empty path when provided.",
                stage="validate_cli_inputs",
                hint="Either omit --data-path or provide a valid directory path.",
            )
        data = Path(data_path)
        if not data.exists() or not data.is_dir():
            raise ConfigurationError(
                f"data_path does not exist or is not a directory: {data}",
                stage="validate_cli_inputs",
                hint="Fix --data-path to point at your raw data directory.",
            )


def validate_run_params(*, pipeline_name: str, run_params: dict[str, Any]) -> None:
    """Validate critical pipeline-specific run parameters."""
    validate_common_inputs(
        line_num=run_params.get("line_num"),
        project_path=run_params.get("project_path"),
        data_path=run_params.get("data_path"),
    )

    if pipeline_name == "ephys":
        channel_name = run_params.get("channel_name")
        if not isinstance(channel_name, str) or not channel_name.strip():
            raise ConfigurationError(
                "channel_name must be a non-empty string.",
                stage="validate_ephys_params",
                hint="Set channel_name in CSV or defaults to a valid channel.",
            )

    if pipeline_name in {"miniscope", "multimodal"}:
        key = "filenames" if pipeline_name == "miniscope" else "miniscope_filenames"
        filenames = run_params.get(key)
        if isinstance(filenames, str):
            run_params[key] = [filenames]
            filenames = run_params[key]
        if filenames is None:
            run_params[key] = []
            filenames = []
        if not isinstance(filenames, list):
            raise ConfigurationError(
                f"{key} must be a list of movie filenames.",
                stage="validate_miniscope_params",
                hint="Use a list such as ['0.avi'] for miniscope input movies.",
            )
        if any((not isinstance(name, str)) or (not name.strip()) for name in filenames):
            raise ConfigurationError(
                f"{key} contains invalid filename values.",
                stage="validate_miniscope_params",
                hint="Ensure all movie names are non-empty strings.",
            )


def apply_headless_policy(*, pipeline_name: str, run_params: dict[str, Any]) -> dict[str, Any]:
    """Apply consistent headless policy across CLI entrypoints."""
    if not bool(run_params.get("headless", False)):
        return run_params

    if pipeline_name in {"ephys", "multimodal"}:
        run_params["plot_channel"] = False
        run_params["plot_spectrogram"] = False
        run_params["plot_phases"] = False

    if pipeline_name in {"miniscope", "multimodal"}:
        run_params["inspect_motion_correction"] = False
        run_params["remove_components_with_gui"] = False
        run_params["plot_params"] = False
        run_params["inline"] = False

    return run_params
