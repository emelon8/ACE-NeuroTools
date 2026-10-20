"""Miniscope acquisition readers and compatibility imports.

Shared analysis lives in :mod:`aceneurotools.calcium_imaging`. Hardware readers
are imported explicitly from ucla_data_manager and onix_miniscope_data_manager.
The historical lightweight exports remain available here.
"""

from aceneurotools.calcium_imaging import (
    PostprocessConfig,
    PostprocessingResult,
    PreprocessConfig,
    PreprocessingResult,
    ProcessConfig,
    ProcessingResult,
    Projections,
)

__all__ = [
    "Projections", "PreprocessConfig", "ProcessConfig", "PostprocessConfig",
    "PreprocessingResult", "ProcessingResult", "PostprocessingResult",
]
