"""ACE-Neuro miniscope subpackage.

Public API
----------
MiniscopeDataManager     — Abstract base + factory for loading calcium imaging data.
UCLADataManager          — UCLA Miniscope V3 reader (.avi + timeStamps.csv).
OnixMiniscopeDataManager — ONIX V4 reader (.raw hardware clock).
MiniscopePreprocessor    — Crop, detrend, ΔF/F normalization.
MiniscopeProcessor       — Motion correction + CNMF-E via CaImAn.
MiniscopePostprocessor   — Component curation GUI, event detection, Hilbert phases.
Projections              — Container for spatial/temporal movie projections.
FilteredMiniscopeData    — Container for bandpass-filtered projection data.
MovieIO                  — Save/load CaImAn movies.

All classes that depend on CaImAn (MiniscopeDataManager and its subclasses,
MiniscopePreprocessor, MiniscopeProcessor, MiniscopePostprocessor, MovieIO)
are NOT eagerly imported here because caiman pulls in tensorflow and requires
NumPy <2. Import them directly from their modules when needed.
"""

from aceneurotools.miniscope.pipeline_results import (
    PostprocessConfig,
    PostprocessingResult,
    PreprocessConfig,
    PreprocessingResult,
    ProcessConfig,
    ProcessingResult,
)
from aceneurotools.miniscope.projections import Projections

__all__ = [
    "Projections",
    "PreprocessingResult",
    "ProcessingResult",
    "PostprocessingResult",
    "PreprocessConfig",
    "ProcessConfig",
    "PostprocessConfig",
    # caiman-dependent — import directly:
    # from aceneurotools.miniscope.miniscope_data_manager import MiniscopeDataManager
    # from aceneurotools.miniscope.ucla_data_manager import UCLADataManager
    # from aceneurotools.miniscope.onix_miniscope_data_manager import OnixMiniscopeDataManager
    # from aceneurotools.miniscope.miniscope_preprocessor import MiniscopePreprocessor
    # from aceneurotools.miniscope.miniscope_processor import MiniscopeProcessor
    # from aceneurotools.miniscope.miniscope_postprocessor import MiniscopePostprocessor
    # from aceneurotools.miniscope.filtered_miniscope_data import FilteredMiniscopeData
    # from aceneurotools.miniscope.movie_io import MovieIO
]
