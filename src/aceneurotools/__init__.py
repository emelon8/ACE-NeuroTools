"""
ACE-neuro: Analysis of Calcium Imaging and Ephys.

Integrated pipelines for calcium imaging and electrophysiology
data processing, analysis, and visualization.

Quick start::

    from aceneurotools.pipelines import EphysPipeline, CalciumImagingPipeline
    from aceneurotools.multimodal import LabConfig
    from aceneurotools.multimodal.stats_loader import load_for_stats
    from aceneurotools.shared import CSVWorker, PathFinder, filter_signal

Subpackages
-----------
aceneurotools.shared      — Cross-cutting utilities: CSV, path-finding, filtering, exceptions.
aceneurotools.ephys       — Ephys data managers, channel processing, visualization.
aceneurotools.calcium_imaging — Shared calcium imaging analysis.
aceneurotools.miniscope       — Miniscope acquisition readers and compatibility imports.
aceneurotools.multimodal  — Alignment utils, statistical engines, lab config.
aceneurotools.pipelines   — High-level CLI orchestrators for all modalities.
"""

try:
    from aceneurotools._version import __version__
except ImportError:
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("aceneurotools")
    except PackageNotFoundError:
        __version__ = "0+unknown"


__all__ = [
    "__version__",
]
