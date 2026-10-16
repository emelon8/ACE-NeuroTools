"""
Configuration utilities for loading analysis parameters.

This module provides functions to load experiment configuration from
CSV files. Project paths must be provided explicitly.
"""

from pathlib import Path
from typing import Any


def load_analysis_params(line_num: int, project_path: Path | None = None) -> dict[str, Any]:
    """Load analysis parameters for an experiment from the project directory.

    Reads from ``project_path/analysis_parameters.csv``.

    Args:
        line_num: Experiment line number (matches 'line number' column in CSV)
        project_path: Path to project directory containing analysis_parameters.csv.
            Required — raises ValueError if not provided.

    Returns:
        Dict of parameters ready to pass to pipeline.run()

    Raises:
        ValueError: If project_path is not provided
        FileNotFoundError: If analysis_parameters.csv doesn't exist
        ValueError: If line_num not found in CSV

    Example:
        >>> params = load_analysis_params(96, project_path=Path("/path/to/project"))
        >>> api = MiniscopePipeline()
        >>> api.run(line_num=96, project_path="/path/to/project", **params)
    """
    from aceneurotools.shared.csv_worker import CSVRowNotFoundError, CSVWorker

    if project_path is None:
        raise ValueError(
            "project_path is required. Pass the path to the directory containing your analysis_parameters.csv."
        )

    active_project = Path(project_path)
    target_csv = active_project / "analysis_parameters.csv"

    if not target_csv.exists():
        raise FileNotFoundError(
            f"Analysis parameters not found: {target_csv}\n"
            f"Make sure project_path is correct (currently: {active_project})"
        )

    try:
        raw = CSVWorker.csv_row_to_dict(target_csv, line_num)
    except CSVRowNotFoundError:
        return {}
    if raw is None:
        raise ValueError(f"Line {line_num} not found in {target_csv}")

    converted = CSVWorker.convert_data_types(raw)
    return parse_analysis_params(converted)


def parse_analysis_params(params: dict[str, Any]) -> dict[str, Any]:
    """Convert CSV column values to pipeline kwargs.

    Maps column names from analysis_parameters.csv to the exact argument
    names expected by MiniscopePipeline.run() and EphysPipeline.run().
    Empty/None values are skipped, allowing pipeline defaults to apply.

    Args:
        params: Dict from CSVWorker.csv_row_to_dict()

    Returns:
        Dict with keys matching pipeline.run() arguments
    """
    from aceneurotools.shared.pipeline_defaults import pipeline_keys

    # Columns that map directly (CSV column name == kwarg name)
    DIRECT_KEYS: list[str] = [
        # Miniscope preprocessing
        "filenames",
        "crop_coords",
        "detrend_method",
        "df_over_f",
        "secs_window",
        "quantile_min",
        # Miniscope processing
        "parallel",
        "n_processes",
        "apply_motion_correction",
        "inspect_motion_correction",
        "plot_params",
        "run_CNMFE",
        "save_estimates",
        "save_CNMFE_estimates_filename",
        "save_CNMFE_params",
        # Miniscope postprocessing
        "remove_components_with_gui",
        "find_calcium_events",
        "derivative_for_estimates",
        "event_height",
        "compute_miniscope_phase",
        "n",
        "cut",
        "ftype",
        "btype",
        "inline",
        "window_length",
        "window_step",
        "freq_lims",
        "time_bandwidth",
        # Ephys
        "channel_name",
        "remove_artifacts",
        "filter_type",
        "filter_range",
        "compute_phases",
        "plot_channel",
        "plot_spectrogram",
        "plot_phases",
        "logging_level",
    ]

    # Columns with different names in CSV vs kwargs
    RENAMED_KEYS: dict[str, str] = {
        "filter_data": "filter_miniscope_data",
        "spectrogram": "compute_miniscope_spectrogram",
        "method": "df_over_f_method",
    }

    args: dict[str, Any] = {}

    direct_keys = set(DIRECT_KEYS) | pipeline_keys("miniscope") | pipeline_keys("ephys") | pipeline_keys("multimodal")
    for key in direct_keys:
        if key in params and params[key] is not None:
            args[key] = params[key]

    crop = args.get("crop")
    if isinstance(crop, (list, tuple)) and len(crop) == 4:
        args.pop("crop")
        args.setdefault("crop_coords", list(crop))
    for csv_key, kwarg_key in RENAMED_KEYS.items():
        if csv_key in params and params[csv_key] is not None:
            args[kwarg_key] = params[csv_key]

    return args


def get_coords_dict_from_analysis_params(miniscope_data_manager: Any) -> tuple[dict[str, int] | None, str]:
    """Read canonical coordinates or the legacy crop tuple through one shared path."""
    params = miniscope_data_manager.analysis_params or {}
    if params.get("crop") is False:
        return None, ""
    coords = params.get("crop_coords")
    if coords is None:
        coords = params.get("crop")
    if isinstance(coords, dict):
        coords = [coords.get(key) for key in ("x0", "y0", "x1", "y1")]
    if isinstance(coords, (list, tuple)) and len(coords) == 4:
        return dict(zip(("x0", "y0", "x1", "y1"), map(int, coords))), "_crop"
    return None, ""
