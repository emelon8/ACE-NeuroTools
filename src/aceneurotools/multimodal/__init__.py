"""
ACE-Neuro multimodal analysis subpackage.

Statistical modules
-------------------
lab_config          — LabConfig and ConditionSpec (lab identity + study design)
stats_config        — StatsConfig and StudyMetadata (algorithm params + study metadata)
stats_loader        — Lightweight data loader (no movie loading; TTL sync + downsampling)
signal_utils        — Pure signal processing utilities (filter, slice, coherence, XC, power,
                      hilbert envelope, filter frequency response)
coherence_analysis  — CoherenceAnalysis engine (spectral power, Welch coherence, XC)
scatter_analysis    — ScatterAnalysis engine (Pearson r, Fisher-z CIs, population violin plots)
event_correlograms  — ACG/CCG/event-correlogram and ISI distribution for event trains
surrogate           — Surrogate event-train generators (jitter/shift/shuffle/resample) for
                      null-distribution testing

Heavy modules (stats_loader, coherence_analysis, scatter_analysis) transitively import
caiman and are NOT eagerly imported here — import them directly when needed.
"""

from aceneurotools.multimodal.event_correlograms import (
    compute_autocorrelogram,
    compute_crosscorrelogram,
    compute_eventcorrelogram,
    compute_isi_distribution,
)
from aceneurotools.multimodal.lab_config import ConditionSpec, LabConfig
from aceneurotools.multimodal.signal_utils import (
    compute_coherence,
    compute_cross_correlation,
    compute_hilbert_envelope,
    compute_signal_stats,
    compute_spectral_power,
    filter_signals,
    get_filter_frequency_response,
    handle_nans,
    normalize_signals_global,
    slice_signal,
    trim_filter_edges,
)
from aceneurotools.multimodal.stats_config import StatsConfig, StudyMetadata
from aceneurotools.multimodal.surrogate import (
    apply_to_group,
    jitter_event_times,
    resample_event_times,
    shift_event_times,
    shuffle_event_intervals,
)

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
    "compute_hilbert_envelope",
    "get_filter_frequency_response",
    # event correlograms
    "compute_autocorrelogram",
    "compute_crosscorrelogram",
    "compute_eventcorrelogram",
    "compute_isi_distribution",
    # surrogate
    "jitter_event_times",
    "shift_event_times",
    "shuffle_event_intervals",
    "resample_event_times",
    "apply_to_group",
    # heavy modules available via direct import:
    # from aceneurotools.multimodal.stats_loader import load_for_stats, load_for_stats_two_channels, load_calcium_signal
    # from aceneurotools.multimodal.coherence_analysis import CoherenceAnalysis, SubjectCoherenceResult
    # from aceneurotools.multimodal.scatter_analysis import ScatterAnalysis, PopulationCorrelationCollector
]
