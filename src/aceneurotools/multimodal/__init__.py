"""
ACE-Neuro multimodal analysis subpackage.

Statistical modules
-------------------
lab_config          — LabConfig and ConditionSpec (lab identity + study design)
stats_config        — StatsConfig and StudyMetadata (algorithm params + study metadata)
stats_loader        — Lightweight data loader (no movie loading; TTL sync + downsampling)
signal_utils        — Pure signal processing utilities (filter, slice, coherence, XC, power)
coherence_analysis  — CoherenceAnalysis engine (spectral power, Welch coherence, XC)
scatter_analysis    — ScatterAnalysis engine (Pearson r, Fisher-z CIs, population violin plots)

Heavy modules (stats_loader, coherence_analysis, scatter_analysis) transitively import
caiman and are NOT eagerly imported here — import them directly when needed.
"""

from aceneurotools.multimodal.lab_config import ConditionSpec, LabConfig
from aceneurotools.multimodal.signal_utils import (
    compute_coherence,
    compute_cross_correlation,
    compute_signal_stats,
    compute_spectral_power,
    filter_signals,
    handle_nans,
    normalize_signals_global,
    slice_signal,
    trim_filter_edges,
)
from aceneurotools.multimodal.stats_config import StatsConfig, StudyMetadata

__all__ = [
    # lab config
    "LabConfig",
    "ConditionSpec",
    # algorithm config
    "StatsConfig",
    "StudyMetadata",
    # signal utils
    "slice_signal",
    "filter_signals",
    "trim_filter_edges",
    "handle_nans",
    "normalize_signals_global",
    "compute_coherence",
    "compute_cross_correlation",
    "compute_spectral_power",
    "compute_signal_stats",
    # heavy modules available via direct import:
    # from aceneurotools.multimodal.stats_loader import load_for_stats, load_for_stats_two_channels, load_calcium_signal
    # from aceneurotools.multimodal.coherence_analysis import CoherenceAnalysis, SubjectCoherenceResult
    # from aceneurotools.multimodal.scatter_analysis import ScatterAnalysis, PopulationCorrelationCollector
]
