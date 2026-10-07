"""Peri-event alignment for continuous signals (LFP, calcium).

Given a 1-D regularly sampled signal and a list of event times (seconds), this
module extracts fixed-window slices around each event and aggregates them into
event-triggered averages or per-event matrices.

Typical use cases:

* LFP aligned to detected slow-wave / spindle peaks
* Mean fluorescence aligned to calcium event onsets
* EEG aligned to TTL stimulus onsets
"""

from __future__ import annotations

import warnings

import numpy as np


def _normalize_window(window: float | tuple[float, float] | list[float]) -> tuple[float, float]:
    """Accept ``window=W`` (symmetric ``[-W, +W]``) or ``window=(b, a)`` and
    return ``(before_s, after_s)`` with both positive.
    """
    if isinstance(window, (int, float)):
        if window <= 0:
            raise ValueError("Scalar window must be > 0.")
        return float(window), float(window)
    if isinstance(window, (tuple, list)) and len(window) == 2:
        before, after = float(window[0]), float(window[1])
        # Allow either sign convention: (-2, 1) or (2, 1)
        before = abs(before)
        after = abs(after)
        if before == 0.0 and after == 0.0:
            raise ValueError("Window must have non-zero duration.")
        return before, after
    raise TypeError("window must be a number or a length-2 (before, after) pair.")


def compute_perievent(
    signal: np.ndarray,
    event_times: np.ndarray,
    fs: float,
    window: float | tuple[float, float] | list[float],
    t_start: float = 0.0,
    drop_boundary_events: bool = True,
) -> dict[str, np.ndarray]:
    """Extract peri-event slices of a regularly sampled signal.

    Parameters
    ----------
    signal : np.ndarray, shape (N,)
        1-D continuous signal.
    event_times : np.ndarray
        Event times in seconds (absolute, i.e. on the same clock as ``t_start``).
    fs : float
        Sampling rate in Hz.
    window : float or (float, float)
        Alignment window. A scalar ``W`` means symmetric ``[-W, +W]``;
        a tuple is ``(before, after)``. Both expressed in seconds.
    t_start : float, default 0.0
        Absolute time of ``signal[0]`` in seconds.
    drop_boundary_events : bool, default True
        If True, drop events whose full window doesn't fit in ``signal``.
        If False, returned slices are NaN-padded to keep all events.

    Returns
    -------
    dict
        Keys:

        * ``time`` — relative time axis (s), shape (n_window_samples,)
        * ``matrix`` — per-event slices, shape (n_kept_events, n_window_samples)
        * ``event_times`` — the original (possibly filtered) event times kept
        * ``n_events`` — int, count of kept events
    """
    if signal.ndim != 1:
        raise ValueError("signal must be 1D.")
    before_s, after_s = _normalize_window(window)
    n_before = int(round(before_s * fs))
    n_after = int(round(after_s * fs))
    n_window = n_before + n_after + 1
    time_axis = (np.arange(n_window) - n_before) / fs

    events = np.asarray(event_times, dtype=np.float64).ravel()
    if events.size == 0:
        return {
            "time": time_axis,
            "matrix": np.zeros((0, n_window), dtype=np.float64),
            "event_times": np.array([], dtype=np.float64),
            "n_events": 0,
        }

    sample_idx = np.round((events - t_start) * fs).astype(np.int64)
    n_samples = signal.size
    in_bounds = (sample_idx - n_before >= 0) & (sample_idx + n_after < n_samples)

    if drop_boundary_events:
        kept_mask = in_bounds
        kept_events = events[kept_mask]
        kept_idx = sample_idx[kept_mask]
        matrix = np.empty((kept_idx.size, n_window), dtype=np.float64)
        for k, idx in enumerate(kept_idx):
            matrix[k] = signal[idx - n_before : idx + n_after + 1]
    else:
        kept_events = events
        matrix = np.full((events.size, n_window), np.nan, dtype=np.float64)
        for k, idx in enumerate(sample_idx):
            lo = idx - n_before
            hi = idx + n_after + 1
            slice_lo = max(0, lo)
            slice_hi = min(n_samples, hi)
            out_lo = slice_lo - lo
            out_hi = out_lo + (slice_hi - slice_lo)
            if slice_hi > slice_lo:
                matrix[k, out_lo:out_hi] = signal[slice_lo:slice_hi]

    return {"time": time_axis, "matrix": matrix, "event_times": kept_events, "n_events": int(matrix.shape[0])}


def compute_event_triggered_average(
    signal: np.ndarray,
    event_times: np.ndarray,
    fs: float,
    window: float | tuple[float, float] | list[float],
    t_start: float = 0.0,
    drop_boundary_events: bool = True,
) -> dict[str, np.ndarray]:
    """Event-triggered average (ETA) of a continuous signal.

    Parameters
    ----------
    signal, event_times, fs, window, t_start, drop_boundary_events :
        See :func:`compute_perievent`.

    Returns
    -------
    dict
        Keys:

        * ``time`` — relative time axis (s)
        * ``mean`` — sample-wise mean across events
        * ``sem`` — sample-wise standard error of the mean
        * ``std`` — sample-wise standard deviation
        * ``matrix`` — per-event matrix (n_events, n_samples)
        * ``n_events`` — number of events that contributed

    Notes
    -----
    With ``drop_boundary_events=False``, NaNs are ignored in the mean / sem /
    std via :func:`numpy.nanmean`-family functions so partially out-of-bound
    events still contribute to the well-defined samples.
    """
    per = compute_perievent(
        signal=signal,
        event_times=event_times,
        fs=fs,
        window=window,
        t_start=t_start,
        drop_boundary_events=drop_boundary_events,
    )
    matrix = per["matrix"]
    n_window = per["time"].size
    if matrix.shape[0] == 0:
        empty = np.zeros(n_window, dtype=np.float64)
        return {"time": per["time"], "mean": empty, "sem": empty, "std": empty, "matrix": matrix, "n_events": 0}

    if drop_boundary_events:
        mean = matrix.mean(axis=0)
        std = matrix.std(axis=0, ddof=1) if matrix.shape[0] > 1 else np.zeros_like(mean)
    else:
        # nanmean/nanstd emit RuntimeWarning for samples with <2 contributing
        # events (degrees-of-freedom degeneracy). That's expected when an event
        # straddles the signal boundary; suppress and let the result carry NaN.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            mean = np.nanmean(matrix, axis=0)
            std = np.nanstd(matrix, axis=0, ddof=1) if matrix.shape[0] > 1 else np.zeros_like(mean)

    n = matrix.shape[0]
    sem = std / np.sqrt(n) if n > 0 else np.zeros_like(mean)

    return {"time": per["time"], "mean": mean, "sem": sem, "std": std, "matrix": matrix, "n_events": n}


def compute_spike_triggered_average(
    signal: np.ndarray,
    spike_times: np.ndarray,
    fs: float,
    window: float | tuple[float, float] | list[float],
    t_start: float = 0.0,
    drop_boundary_events: bool = True,
) -> dict[str, np.ndarray]:
    """Alias for :func:`compute_event_triggered_average` with spike-train semantics.

    Provided for API symmetry with neighbouring analyses; the implementation
    is identical.
    """
    return compute_event_triggered_average(
        signal=signal,
        event_times=spike_times,
        fs=fs,
        window=window,
        t_start=t_start,
        drop_boundary_events=drop_boundary_events,
    )


# ---------------------------------------------------------------------------
# Legacy API
# ---------------------------------------------------------------------------


def spike_trig_avg(eventArray: np.ndarray, dataArray: np.ndarray, framesb: int, framesa: int) -> dict[int, np.ndarray]:
    """
    Compute the average spike values starting 'framesb' before the event
    and ending 'framesa' after the event.

    .. deprecated::
       Use :func:`aceneurotools.stats.perievent.compute_event_triggered_average`
       which operates on signals + event times in seconds and returns the
       mean alongside per-event SEM/std/matrix.

    Args:
        eventArray: A numpy array of when and/or where events occur. Can either
                    be in the format of [[component, frame],...] or
                    [[frame],...]
        dataArray: A numpy array of the signal values at each frame.
        framesb: Number of frames before the event to include.
        framesa: Number of frames after the event to include.
    Returns:
        avgEventDict: a dictionary dictionary where the keys represent the
                      component number from the dataArray and the value is
                      a numpy array of the average values at each frame
                      of the designated window around the event
    """
    warnings.warn(
        "spike_trig_avg is deprecated; use "
        "aceneurotools.stats.perievent.compute_event_triggered_average "
        "for a sample-rate-aware peri-event average.",
        DeprecationWarning,
        stacklevel=2,
    )
    avgEventDict: dict[int, np.ndarray] = {}
    if dataArray.ndim == 1:
        valid_events = 0
        for event in eventArray:
            idx = int(event[0])
            if idx >= framesb and idx <= dataArray.size - framesa - 1:
                chunk = dataArray[idx - framesb : idx + framesa + 1]
                if 0 in avgEventDict:
                    avgEventDict[0] = avgEventDict[0] + chunk
                else:
                    avgEventDict[0] = chunk.astype(float)
                valid_events += 1
        if 0 in avgEventDict and valid_events > 0:
            avgEventDict[0] /= valid_events
    else:
        for event in eventArray:
            comp = int(event[0])
            idx = int(event[1])
            if idx >= framesb and idx <= dataArray[comp].size - framesa - 1:
                chunk = dataArray[comp][idx - framesb : idx + framesa + 1]
                if comp in avgEventDict:
                    avgEventDict[comp] = avgEventDict[comp] + chunk
                else:
                    avgEventDict[comp] = chunk.astype(float)

        for component in avgEventDict:
            num_events = len(np.argwhere(eventArray[:, 0] == component))
            if num_events > 0:
                avgEventDict[component] /= num_events
    return avgEventDict
