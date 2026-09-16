"""Band-limited oscillatory event detection.

Detects oscillatory bursts (spindles, slow waves, K-complexes, propofol-alpha,
beta/gamma transients) in continuous LFP. The pipeline is:

1. Bandpass-filter the signal to the target frequency band.
2. Compute the Hilbert envelope.
3. Sliding-window smooth.
4. Z-score the smoothed envelope.
5. Threshold against a (lower, upper) band; intervals where the z-score is
   above the lower threshold and below the upper threshold are candidate
   events.
6. Drop intervals outside the (min, max) duration band.
7. Merge events separated by less than ``min_interval``.
8. Per surviving event, record peak amplitude, peak-time, and band-limited
   power (dB).

Operates on plain numpy arrays (no ea.``Channel`` dependency at this level —
ea-side callers can wrap ``Channel.signal`` directly).
"""

from __future__ import annotations

import numpy as np

from aceneurotools.stats.signal_utils import (
    compute_hilbert_envelope,
    filter_signals,
)


def _threshold_intervals(
    above: np.ndarray,
    fs: float,
    t_start: float = 0.0,
) -> np.ndarray:
    """Find contiguous True runs and return their (start_s, end_s) bounds.

    Parameters
    ----------
    above : np.ndarray, dtype=bool
        Boolean mask, length N.
    fs : float
        Sampling rate of the underlying signal (Hz).
    t_start : float, default 0.0
        Absolute time (s) of sample index 0 — added to each interval.

    Returns
    -------
    np.ndarray, shape (n_intervals, 2)
        Per-row ``[start_s, end_s]``. Empty if no intervals.
    """
    if above.size == 0:
        return np.zeros((0, 2), dtype=np.float64)
    diff = np.diff(above.astype(np.int8), prepend=0, append=0)
    starts = np.flatnonzero(diff == 1)
    ends = np.flatnonzero(diff == -1)
    # `ends` are exclusive sample indices; convert to inclusive end time
    if starts.size == 0:
        return np.zeros((0, 2), dtype=np.float64)
    starts_t = t_start + starts / fs
    ends_t = t_start + (ends - 1) / fs
    return np.column_stack([starts_t, ends_t])


def _drop_short(intervals: np.ndarray, min_duration: float) -> np.ndarray:
    if intervals.size == 0:
        return intervals
    keep = (intervals[:, 1] - intervals[:, 0]) >= min_duration
    return intervals[keep]


def _drop_long(intervals: np.ndarray, max_duration: float) -> np.ndarray:
    if intervals.size == 0:
        return intervals
    keep = (intervals[:, 1] - intervals[:, 0]) <= max_duration
    return intervals[keep]


def _merge_close(intervals: np.ndarray, min_gap: float) -> np.ndarray:
    """Merge intervals separated by less than ``min_gap`` seconds."""
    if intervals.shape[0] < 2:
        return intervals
    out = [intervals[0].copy()]
    for s, e in intervals[1:]:
        if s - out[-1][1] < min_gap:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append(np.array([s, e]))
    return np.asarray(out, dtype=np.float64)


def detect_oscillatory_events(
    signal: np.ndarray,
    fs: float,
    frequency_band: tuple[float, float],
    threshold_band: tuple[float, float],
    duration_band: tuple[float, float],
    min_interval: float,
    sliding_window_samples: int = 51,
    t_start: float = 0.0,
    filter_order: int = 2,
) -> dict[str, np.ndarray]:
    """Detect oscillatory bursts in a 1D signal.

    Parameters
    ----------
    signal : np.ndarray, shape (N,)
        Continuous time series (e.g. one ephys channel).
    fs : float
        Sampling rate in Hz.
    frequency_band : (float, float)
        ``(low, high)`` bandpass cutoff in Hz.
    threshold_band : (float, float)
        ``(lower, upper)`` z-score thresholds applied to the smoothed envelope.
        A sample is considered "active" when the z-score is at or above
        ``lower`` and at or below ``upper``.
    duration_band : (float, float)
        ``(min, max)`` event duration in seconds.
    min_interval : float
        Minimum gap (s) between consecutive events; closer pairs are merged.
    sliding_window_samples : int, default 51
        Boxcar smoothing window length in samples (applied to the envelope).
    t_start : float, default 0.0
        Absolute time (s) of ``signal[0]``. Returned event times are absolute.
    filter_order : int, default 2
        Butterworth filter order (matches :func:`filter_signals`).

    Returns
    -------
    dict
        Keys:

        * ``start`` — event start times (s), shape (n_events,)
        * ``end`` — event end times (s), shape (n_events,)
        * ``power_db`` — mean envelope power in dB per event
        * ``amplitude`` — peak envelope amplitude per event
        * ``peak_time`` — absolute time (s) of the envelope peak per event

        All arrays have the same length; ``n_events == 0`` returns
        zero-length arrays.

    Examples
    --------
    Detect ripple-like events (150–250 Hz) lasting 25–100 ms, separated by
    at least 30 ms::

        result = detect_oscillatory_events(
            signal,
            fs=1000.0,
            frequency_band=(150, 250),
            threshold_band=(2.0, np.inf),
            duration_band=(0.025, 0.100),
            min_interval=0.030,
        )
    """
    if signal.ndim != 1:
        raise ValueError("signal must be 1D.")
    if np.var(signal) == 0:
        empty = np.array([], dtype=np.float64)
        return {"start": empty, "end": empty, "power_db": empty,
                "amplitude": empty, "peak_time": empty}
    if frequency_band[0] >= frequency_band[1]:
        raise ValueError("frequency_band must be (low, high) with low < high.")
    if threshold_band[0] >= threshold_band[1]:
        raise ValueError("threshold_band must be (lower, upper) with lower < upper.")
    if duration_band[0] >= duration_band[1]:
        raise ValueError("duration_band must be (min, max) with min < max.")
    if min_interval < 0:
        raise ValueError("min_interval must be >= 0.")
    if sliding_window_samples <= 0:
        raise ValueError("sliding_window_samples must be > 0.")

    # 1. Bandpass — filter_signals takes a pair; duplicate the input and ignore
    #    the second output (cheap; same length).
    filtered, _ = filter_signals(signal, signal, fs, list(frequency_band), order=filter_order)

    # 2. Hilbert envelope.
    envelope = compute_hilbert_envelope(filtered)

    # 3. Boxcar smoothing (same length as input).
    kernel = np.ones(sliding_window_samples) / sliding_window_samples
    smoothed = np.convolve(envelope, kernel, mode="same")

    # 4. Z-score the smoothed envelope.
    mean = float(np.mean(smoothed))
    std = float(np.std(smoothed))
    if std == 0:
        # Degenerate input — nothing to detect.
        empty = np.array([], dtype=np.float64)
        return {"start": empty, "end": empty, "power_db": empty,
                "amplitude": empty, "peak_time": empty}
    zscored = (smoothed - mean) / std

    # 5. Threshold.
    above = (zscored >= threshold_band[0]) & (zscored <= threshold_band[1])
    intervals = _threshold_intervals(above, fs, t_start=t_start)

    # 6. Duration filtering.
    intervals = _drop_short(intervals, duration_band[0])
    intervals = _drop_long(intervals, duration_band[1])

    # 7. Merge close intervals.
    intervals = _merge_close(intervals, min_interval)

    if intervals.size == 0:
        empty = np.array([], dtype=np.float64)
        return {"start": empty, "end": empty, "power_db": empty,
                "amplitude": empty, "peak_time": empty}

    # 8. Per-event metadata: power_dB, amplitude, peak_time.
    powers = np.empty(intervals.shape[0], dtype=np.float64)
    amps = np.empty(intervals.shape[0], dtype=np.float64)
    peaks = np.empty(intervals.shape[0], dtype=np.float64)
    for k, (s, e) in enumerate(intervals):
        i0 = max(0, int(np.floor((s - t_start) * fs)))
        i1 = min(envelope.size, int(np.ceil((e - t_start) * fs)) + 1)
        seg = envelope[i0:i1]
        if seg.size == 0:
            powers[k] = np.nan
            amps[k] = np.nan
            peaks[k] = np.nan
            continue
        p = float(np.mean(seg ** 2))
        powers[k] = 10.0 * np.log10(p) if p > 0 else np.nan
        peak_idx = int(np.argmax(seg))
        amps[k] = float(seg[peak_idx])
        peaks[k] = t_start + (i0 + peak_idx) / fs

    return {
        "start": intervals[:, 0].astype(np.float64),
        "end": intervals[:, 1].astype(np.float64),
        "power_db": powers,
        "amplitude": amps,
        "peak_time": peaks,
    }
