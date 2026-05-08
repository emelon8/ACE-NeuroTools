"""Shared utilities for ACE-NeuroTools."""

from aceneurotools.shared.exceptions import (
    AceNeuroError,
    ConfigurationError,
    DataFormatError,
    DataIntegrityError,
    DataImportError,
    DataNotFoundError,
    PipelineExecutionError,
    ProcessingError,
    format_error_message,
    print_cli_error,
)

__all__ = [
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
]
