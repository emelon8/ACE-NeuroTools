"""Shared utilities for ACE-neuro.

Public API
----------
Exceptions (from shared.exceptions)
  AceNeuroError, ConfigurationError, DataFormatError, DataIntegrityError,
  DataImportError, DataNotFoundError, PipelineExecutionError, ProcessingError,
  format_error_message, print_cli_error

Data utilities
  CSVWorker            — CSV row loading and type conversion.
  PathFinder           — Recursive file discovery by suffix/prefix.
  ExperimentDataManager — Reads experiments.csv + analysis_parameters.csv.

Signal processing
  filter_signal        — Canonical FIR / Butterworth zero-phase filter.
  filter_data          — Backward-compatible alias (delegates to filter_signal).

Plotting
  set_backend          — Set matplotlib backend once at CLI entry points.
"""

from aceneurotools.shared.csv_worker import CSVWorker
from aceneurotools.shared.exceptions import (
    AceNeuroError,
    ConfigurationError,
    DataFormatError,
    DataImportError,
    DataIntegrityError,
    DataNotFoundError,
    PipelineExecutionError,
    ProcessingError,
    format_error_message,
    print_cli_error,
)
from aceneurotools.shared.experiment_data_manager import ExperimentDataManager
from aceneurotools.shared.path_finder import PathFinder
from aceneurotools.shared.plotting import set_backend
from aceneurotools.shared.signal_processing import filter_data, filter_signal

__all__ = [
    # Exceptions
    "AceNeuroError",
    "ConfigurationError",
    "DataFormatError",
    "DataIntegrityError",
    "DataImportError",
    "DataNotFoundError",
    "PipelineExecutionError",
    "ProcessingError",
    "format_error_message",
    "print_cli_error",
    # Data utilities
    "CSVWorker",
    "PathFinder",
    "ExperimentDataManager",
    # Signal processing
    "filter_signal",
    "filter_data",
    # Plotting
    "set_backend",
]
