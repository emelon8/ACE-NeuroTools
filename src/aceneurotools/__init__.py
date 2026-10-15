"""
ACE-neuro: Analysis of Calcium Imaging and Ephys.

Integrated pipelines for miniscope calcium imaging and electrophysiology
data processing, analysis, and visualization.

Quick start::

    from aceneurotools.pipelines import EphysPipeline, MiniscopePipeline
    from aceneurotools.config import LabConfig
    from aceneurotools.stats.loader import load_for_stats
    from aceneurotools.shared import CSVWorker, PathFinder, filter_signal

Subpackages
-----------
aceneurotools.shared      — Cross-cutting utilities: CSV, path-finding, filtering, exceptions.
aceneurotools.config      — Configuration loading: lab_config.json, stats_config.json,
                            analysis_parameters.csv.
aceneurotools.ephys       — Ephys data managers, channel processing, visualization.
aceneurotools.miniscope   — Calcium imaging data managers, pre/processor, postprocessor.
aceneurotools.multimodal  — Miniscope ↔ ephys alignment and phase-locking.
aceneurotools.stats       — Statistical engines (coherence, scatter) + modular toolbox
                            (surrogates, wavelets, oscillatory events, correlograms).
aceneurotools.pipelines   — High-level CLI orchestrators for all modalities.
"""

__version__ = "0.1.0"

__all__ = [
    "__version__",
]
