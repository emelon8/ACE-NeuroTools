"""
Configuration utilities for loading analysis parameters.

This module provides functions to load experiment configuration from
CSV files (new method) with deprecated support for YAML configs.
"""

import warnings
from typing import Dict, Any, Optional
from pathlib import Path


def load_analysis_params(line_num: int, project_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load analysis parameters for an experiment from the active project.
    
    Reads from PROJECT_REPO/analysis_parameters.csv as configured in .env,
    or from the provided project_path.
    
    Args:
        line_num: Experiment line number (matches 'line number' column in CSV)
        project_path: Optional path to project directory containing analysis_parameters.csv
    
    Returns:
        Dict of parameters ready to pass to pipeline.run()
    
    Raises:
        FileNotFoundError: If analysis_parameters.csv doesn't exist
        ValueError: If line_num not found in CSV
    
    Example:
        >>> params = load_analysis_params(96)
        >>> api = MiniscopePipeline()
        >>> api.run(line_num=96, **params)
    """
    from src2.shared.paths import ANALYSIS_PARAMS
    from src2.shared.csv_worker import CSVWorker
    
    if project_path:
        target_csv = project_path / "analysis_parameters.csv"
    else:
        target_csv = ANALYSIS_PARAMS
    
    if not target_csv.exists():
        raise FileNotFoundError(
            f"Analysis parameters not found: {target_csv}\n"
            f"Make sure PROJECT_REPO is set correctly in your .env file or project_path is valid."
        )
    
    raw = CSVWorker.csv_row_to_dict(target_csv, line_num)
    if raw is None:
        raise ValueError(f"Line {line_num} not found in {target_csv}")
    
    converted = CSVWorker.convert_data_types(raw)
    return parse_analysis_params(converted)


def parse_analysis_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Convert CSV column values to pipeline kwargs.
    
    Maps column names from analysis_parameters.csv to the exact argument
    names expected by MiniscopePipeline.run() and EphysPipeline.run().
    Empty/None values are skipped, allowing pipeline defaults to apply.
    
    Args:
        params: Dict from CSVWorker.csv_row_to_dict()
    
    Returns:
        Dict with keys matching pipeline.run() arguments
    """
    # Columns that map directly (CSV column name == kwarg name)
    DIRECT_KEYS = [
        # Miniscope preprocessing
        'filenames',
        'detrend_method', 'df_over_f', 'secs_window', 'quantile_min',
        # Miniscope processing
        'parallel', 'n_processes', 'apply_motion_correction',
        'inspect_motion_correction', 'plot_params',
        'run_CNMFE', 'save_estimates', 'save_CNMFE_estimates_filename',
        'save_CNMFE_params',
        # Miniscope postprocessing
        'remove_components_with_gui', 'find_calcium_events',
        'derivative_for_estimates', 'event_height',
        'compute_miniscope_phase', 'n', 'cut', 'ftype', 'btype', 'inline',
        'window_length', 'window_step', 'freq_lims', 'time_bandwidth',
        # Ephys
        'channel_name', 'remove_artifacts', 'filter_type', 'filter_range',
        'compute_phases', 'plot_channel', 'plot_spectrogram', 'plot_phases',
        'logging_level'
    ]
    
    # Columns with different names in CSV vs kwargs
    RENAMED_KEYS = {
        'filter_data': 'filter_miniscope_data',
        'spectrogram': 'compute_miniscope_spectrogram',
        'method': 'df_over_f_method',
    }
    
    args = {}
    
    for key in DIRECT_KEYS:
        if key in params and params[key] is not None:
            args[key] = params[key]
    
    for csv_key, kwarg_key in RENAMED_KEYS.items():
        if csv_key in params and params[csv_key] is not None:
            args[kwarg_key] = params[csv_key]
    
    return args
