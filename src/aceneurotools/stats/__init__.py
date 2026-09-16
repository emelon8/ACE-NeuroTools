"""ACE-NeuroTools statistical analysis subpackage.

Analysis engines (orchestrated by ``aceneurotools.pipelines.stats``)
--------------------------------------------------------------------
loader              — Lightweight data loader (no movie loading; TTL sync + downsampling)
coherence_analysis  — CoherenceAnalysis engine (spectral power, Welch coherence, XC)
scatter_analysis    — ScatterAnalysis engine (Pearson r, Fisher-z CIs, population violin plots)

Modular toolbox (library-only, importable a la carte)
-----------------------------------------------------
signal_utils        — Pure signal processing utilities (filter, slice, coherence, XC, power,
                      hilbert envelope, filter frequency response)
event_correlograms  — ACG/CCG/event-correlogram and ISI distribution for event trains
surrogate           — Surrogate event-train generators (jitter/shift/shuffle/resample) for
                      null-distribution testing
oscillatory_events  — Band-limited oscillatory burst detection (slow waves, spindles,
                      K-complexes, propofol-alpha) via envelope thresholding
perievent           — Peri-event slice extraction + event/spike-triggered averages on
                      regularly sampled signals
wavelets            — Morlet continuous wavelet transform (time-frequency analysis)

Heavy modules (loader, coherence_analysis, scatter_analysis) transitively import
caiman and are NOT eagerly imported here — import them directly when needed::

    from aceneurotools.stats.loader import load_for_stats, load_calcium_signal
    from aceneurotools.stats.coherence_analysis import CoherenceAnalysis
    from aceneurotools.stats.scatter_analysis import ScatterAnalysis
"""

from aceneurotools.stats.event_correlograms import (
    compute_autocorrelogram,
    compute_crosscorrelogram,
    compute_eventcorrelogram,
    compute_isi_distribution,
)
from aceneurotools.stats.oscillatory_events import detect_oscillatory_events
from aceneurotools.stats.perievent import (
    compute_event_triggered_average,
    compute_perievent,
    compute_spike_triggered_average,
)
from aceneurotools.stats.signal_utils import (
    compute_coherence,
    compute_cross_correlation,
    compute_hilbert_envelope,
    compute_mutual_information,
    compute_signal_stats,
    compute_spectral_power,
    filter_signals,
    get_filter_frequency_response,
    handle_nans,
    normalize_signals_global,
    slice_signal,
    trim_filter_edges,
)
from aceneurotools.stats.surrogate import (
    PermutationTestResult,
    apply_to_group,
    jitter_event_times,
    permutation_test,
    resample_event_times,
    shift_event_times,
    shuffle_event_intervals,
)
from aceneurotools.stats.wavelets import (
    compute_wavelet_transform,
    generate_morlet_filterbank,
)

__all__ = [
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
    "compute_mutual_information",
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
    "permutation_test",
    "PermutationTestResult",
    # oscillatory events
    "detect_oscillatory_events",
    # perievent
    "compute_perievent",
    "compute_event_triggered_average",
    "compute_spike_triggered_average",
    # wavelets
    "compute_wavelet_transform",
    "generate_morlet_filterbank",
]
