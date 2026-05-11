"""Stateless signal processing utilities for the stats pipeline."""

from __future__ import annotations

import warnings

import numpy as np
from scipy.signal import butter, correlate, correlation_lags, filtfilt
from scipy.signal import coherence as scipy_coherence


def slice_signal(
    signal: np.ndarray,
    selections: dict[int, list[list[float]]],
    line_num: int,
    fr: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (control, treatment) segments. Time windows are in minutes."""
    if line_num not in selections:
        raise KeyError(
            f"line_num {line_num} not found in selections dict.  "
            "Add it via StudyMetadata or --stats-metadata-path."
        )
    windows = selections[line_num]
    samples_per_min = fr * 60.0

    ctrl_start = int(windows[0][0] * samples_per_min)
    ctrl_end   = int(windows[0][1] * samples_per_min)
    treat_start = int(windows[1][0] * samples_per_min)
    treat_end   = int(windows[1][1] * samples_per_min)

    # Clamp to signal length
    n = len(signal)
    ctrl_end    = min(ctrl_end,   n)
    treat_end   = min(treat_end,  n)

    return signal[ctrl_start:ctrl_end], signal[treat_start:treat_end]


def filter_signals(
    signal_1: np.ndarray,
    signal_2: np.ndarray,
    fr: float,
    freq_range: list[float],
    order: int = 2,
) -> tuple[np.ndarray, np.ndarray]:
    """Zero-phase Butterworth bandpass filter applied to two signals."""
    nyq = 0.5 * fr
    low  = freq_range[0] / nyq
    high = freq_range[1] / nyq
    b, a = butter(order, [low, high], btype="band")
    return filtfilt(b, a, signal_1), filtfilt(b, a, signal_2)


def trim_filter_edges(signal: np.ndarray, fr: float, trim_seconds: float = 5.0) -> np.ndarray:
    """Trim edge samples to remove Butterworth transients."""
    trim_samples = int(trim_seconds * fr)
    if trim_samples == 0:
        return signal
    if 2 * trim_samples >= len(signal):
        warnings.warn(
            f"Signal length {len(signal)} < 2 × trim ({2 * trim_samples} samples) — skipping trim.",
            stacklevel=2,
        )
        return signal
    return signal[trim_samples:-trim_samples]


def handle_nans(
    signal: np.ndarray,
    fr: float,
    max_gap_seconds: float = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate short NaN gaps (<= max_gap_seconds); zero and mask long ones."""
    nan_mask = np.isnan(signal)
    if not np.any(nan_mask):
        return signal.copy(), np.ones(len(signal), dtype=bool)

    max_gap_samples = int(max_gap_seconds * fr)
    valid_mask = np.ones(len(signal), dtype=bool)
    cleaned = signal.copy()

    nan_int  = nan_mask.astype(int)
    nan_diff = np.diff(np.concatenate([[0], nan_int, [0]]))
    starts   = np.where(nan_diff == 1)[0]
    ends     = np.where(nan_diff == -1)[0]

    n_interpolated = 0
    n_excluded     = 0

    for start, end in zip(starts, ends):
        gap = end - start
        if gap <= max_gap_samples:
            # Linear interpolation between adjacent valid values
            left  = cleaned[start - 1] if start > 0 else 0.0
            right = (
                cleaned[end]
                if end < len(signal) and not np.isnan(cleaned[end])
                else left
            )
            cleaned[start:end] = np.linspace(left, right, gap + 2)[1:-1]
            n_interpolated += gap
        else:
            valid_mask[start:end] = False
            cleaned[start:end] = 0.0
            n_excluded += gap

    if n_interpolated > 0 or n_excluded > 0:
        print(
            f"    NaN handling: {n_interpolated} samples interpolated, "
            f"{n_excluded} samples excluded."
        )

    return cleaned, valid_mask


def normalize_signals_global(
    control_1: np.ndarray,
    treatment_1: np.ndarray,
    control_2: np.ndarray,
    treatment_2: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict]:
    """Z-score four segments with pooled ctrl+treat stats so both periods share the same scale."""
    all_1 = np.concatenate([control_1, treatment_1])
    all_2 = np.concatenate([control_2, treatment_2])

    mean_1 = float(np.nanmean(all_1))
    std_1  = float(np.nanstd(all_1))
    mean_2 = float(np.nanmean(all_2))
    std_2  = float(np.nanstd(all_2))

    def _zscore(arr: np.ndarray, mean: float, std: float) -> np.ndarray:
        if std == 0 or np.isnan(std):
            return np.zeros_like(arr)
        return (arr - mean) / std

    params = {
        "method": "zscore",
        "global": True,
        "signal_1_mean": mean_1,
        "signal_1_std": std_1,
        "signal_2_mean": mean_2,
        "signal_2_std": std_2,
    }
    return (
        _zscore(control_1,   mean_1, std_1),
        _zscore(treatment_1, mean_1, std_1),
        _zscore(control_2,   mean_2, std_2),
        _zscore(treatment_2, mean_2, std_2),
        params,
    )


def compute_coherence(
    signal_1: np.ndarray,
    signal_2: np.ndarray,
    fr: float,
    freq_range: list[float],
    nperseg_seconds: float | None = None,
) -> float:
    """Mean squared coherence in freq_range via Welch. nperseg_seconds=None uses scipy's default (256 samples)."""
    nperseg = int(fr * nperseg_seconds) if nperseg_seconds is not None else None
    f, cxy = scipy_coherence(signal_1, signal_2, fs=fr, nperseg=nperseg)
    mask = (f >= freq_range[0]) & (f <= freq_range[1])
    return float(np.mean(cxy[mask])) if np.any(mask) else float("nan")


def compute_cross_correlation(
    signal_1: np.ndarray,
    signal_2: np.ndarray,
    fr: float,
    max_lag_seconds: float = 10.0,
) -> tuple[float, float]:
    """Peak normalized cross-correlation and lag in seconds. Positive lag = signal_2 is delayed."""
    norm_1 = (signal_1 - np.mean(signal_1)) / (np.std(signal_1) * len(signal_1) + 1e-12)
    norm_2 = (signal_2 - np.mean(signal_2)) / (np.std(signal_2) + 1e-12)

    nxcorr = correlate(norm_2, norm_1, mode="full")
    lags   = correlation_lags(len(norm_1), len(norm_2), mode="full") / fr

    mask   = (lags >= -max_lag_seconds) & (lags <= max_lag_seconds)
    nxcorr = nxcorr[mask]
    lags   = lags[mask]

    peak_idx = int(np.argmax(nxcorr))
    return float(nxcorr[peak_idx]), float(lags[peak_idx])


def compute_spectral_power(
    signal: np.ndarray,
    fr: float,
    freq_range: list[float],
    window_length: float = 60.0,
    window_step: float = 3.0,
    time_bandwidth: float = 2.0,
) -> float:
    """Mean power in freq_range (dB) via multitaper spectrogram (Prerau lab implementation)."""
    from aceneurotools.shared.multitaper_spectrogram_python import multitaper_spectrogram

    num_tapers = int(time_bandwidth * 2 - 1)
    power_matrix, _times, frequencies = multitaper_spectrogram(
        signal,
        fr,
        frequency_range=[0.0, fr / 2],
        time_bandwidth=time_bandwidth,
        num_tapers=num_tapers,
        window_params=[window_length, window_step],
        min_nfft=0,
        detrend_opt="constant",
        multiprocess=True,
        n_jobs=3,
        weighting="unity",
        plot_on=False,
        return_fig=False,
        clim_scale=False,
        verbose=False,
        xyflip=False,
    )
    power_db = 10.0 * np.log10(power_matrix + 1e-30)
    freq_mask = (frequencies >= freq_range[0]) & (frequencies <= freq_range[1])
    return float(np.mean(power_db[freq_mask])) if np.any(freq_mask) else float("nan")


def compute_signal_stats(
    signal_1: np.ndarray,
    signal_2: np.ndarray,
    fr: float,
    freq_range: list[float],
    window_length: float = 60.0,
    window_step: float = 3.0,
    time_bandwidth: float = 2.0,
    coherence_nperseg_seconds: float | None = None,
) -> list[float]:
    """Returns [power_1, power_2, coherence, xc, lag] for a signal pair."""
    power_1 = compute_spectral_power(signal_1, fr, freq_range, window_length, window_step, time_bandwidth)
    power_2 = compute_spectral_power(signal_2, fr, freq_range, window_length, window_step, time_bandwidth)
    coh     = compute_coherence(signal_1, signal_2, fr, freq_range, coherence_nperseg_seconds)
    xc, lag = compute_cross_correlation(signal_1, signal_2, fr)
    return [power_1, power_2, coh, xc, lag]
