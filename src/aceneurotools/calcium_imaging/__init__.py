"""Shared calcium imaging analysis for supported acquisition formats.

Import processors and data managers from their modules to load CaImAn only
when needed. UCLA and ONIX acquisition readers remain in aceneurotools.miniscope.
"""

from aceneurotools.calcium_imaging.pipeline_results import (
    PostprocessConfig,
    PostprocessingResult,
    PreprocessConfig,
    PreprocessingResult,
    ProcessConfig,
    ProcessingResult,
)
from aceneurotools.calcium_imaging.projections import Projections

__all__ = [
    "Projections", "PreprocessConfig", "ProcessConfig", "PostprocessConfig",
    "PreprocessingResult", "ProcessingResult", "PostprocessingResult",
]
