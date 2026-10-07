"""Tests for aceneurotools.multimodal.oscillatory_events."""

from __future__ import annotations

import numpy as np
import pytest

from aceneurotools.multimodal.oscillatory_events import (
    _drop_long,
    _drop_short,
    _merge_close,
    _threshold_intervals,
    detect_oscillatory_events,
)

# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------


def test_threshold_intervals_simple_runs():
    above = np.array([0, 1, 1, 1, 0, 0, 1, 1, 0, 1], dtype=bool)
    iv = _threshold_intervals(above, fs=10.0, t_start=0.0)
    # Three runs: [1:3], [6:7], [9:9]
    assert iv.shape == (3, 2)
    # First run: starts at sample 1 (0.1s), ends at sample 3 inclusive (0.3s)
    assert iv[0, 0] == pytest.approx(0.1)
    assert iv[0, 1] == pytest.approx(0.3)


def test_threshold_intervals_empty():
    iv = _threshold_intervals(np.array([], dtype=bool), fs=100.0)
    assert iv.shape == (0, 2)


def test_drop_short_keeps_long_enough():
    iv = np.array([[0.0, 0.05], [1.0, 1.3], [2.0, 2.01]])
    out = _drop_short(iv, min_duration=0.1)
    assert out.shape == (1, 2)
    assert out[0, 0] == 1.0


def test_drop_long_keeps_short_enough():
    iv = np.array([[0.0, 5.0], [1.0, 1.3], [2.0, 10.0]])
    out = _drop_long(iv, max_duration=2.0)
    assert out.shape == (1, 2)
    assert out[0, 0] == 1.0


def test_merge_close_combines_neighbors():
    iv = np.array([[0.0, 1.0], [1.05, 2.0], [3.0, 4.0]])
    out = _merge_close(iv, min_gap=0.1)
    assert out.shape == (2, 2)
    assert out[0, 1] == pytest.approx(2.0)
    assert out[1, 0] == pytest.approx(3.0)


def test_merge_close_no_merge_when_far():
    iv = np.array([[0.0, 1.0], [2.0, 3.0]])
    out = _merge_close(iv, min_gap=0.1)
    assert out.shape == (2, 2)


# ---------------------------------------------------------------------------
# detect_oscillatory_events
# ---------------------------------------------------------------------------


def _signal_with_bursts(
    fs: float = 1000.0,
    duration: float = 10.0,
    burst_freq: float = 50.0,
    burst_times: tuple[float, ...] = (2.0, 5.0, 8.0),
    burst_duration: float = 0.2,
    noise_std: float = 0.05,
    seed: int = 0,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(0.0, duration, 1.0 / fs)
    sig = noise_std * rng.standard_normal(t.size)
    for t0 in burst_times:
        mask = (t >= t0) & (t < t0 + burst_duration)
        sig[mask] += 1.5 * np.cos(2 * np.pi * burst_freq * (t[mask] - t0))
    return sig


def test_detect_finds_known_bursts():
    fs = 1000.0
    sig = _signal_with_bursts(fs=fs, burst_times=(2.0, 5.0, 8.0))
    result = detect_oscillatory_events(
        sig,
        fs=fs,
        frequency_band=(40.0, 60.0),
        threshold_band=(1.0, np.inf),
        duration_band=(0.05, 1.0),
        min_interval=0.1,
        sliding_window_samples=51,
    )
    # We injected 3 bursts; detection should find ~3 events near the injected times.
    assert result["start"].size >= 3
    for expected in (2.0, 5.0, 8.0):
        # nearest detected start should be within ~50 ms of injection
        nearest = np.min(np.abs(result["start"] - expected))
        assert nearest < 0.05


def test_detect_returns_consistent_array_lengths():
    fs = 500.0
    sig = _signal_with_bursts(fs=fs, burst_times=(1.0, 3.0))
    result = detect_oscillatory_events(
        sig,
        fs=fs,
        frequency_band=(40.0, 60.0),
        threshold_band=(1.0, np.inf),
        duration_band=(0.05, 1.0),
        min_interval=0.05,
    )
    n = result["start"].size
    for key in ("end", "power_db", "amplitude", "peak_time"):
        assert result[key].size == n


def test_detect_drops_too_short_events():
    fs = 1000.0
    # 50 ms bursts; require >= 500 ms — bandpass-filter impulse response
    # broadens the burst by ~50 ms, but not enough to clear 500 ms.
    sig = _signal_with_bursts(fs=fs, burst_times=(2.0, 5.0), burst_duration=0.05)
    result = detect_oscillatory_events(
        sig,
        fs=fs,
        frequency_band=(40.0, 60.0),
        threshold_band=(1.0, np.inf),
        duration_band=(0.5, 2.0),
        min_interval=0.05,
        sliding_window_samples=5,
    )
    assert result["start"].size == 0


def test_detect_returns_empty_for_pure_noise():
    rng = np.random.default_rng(42)
    sig = 0.1 * rng.standard_normal(5000)
    result = detect_oscillatory_events(
        sig,
        fs=1000.0,
        frequency_band=(40.0, 60.0),
        threshold_band=(5.0, np.inf),  # very high threshold
        duration_band=(0.1, 1.0),
        min_interval=0.05,
    )
    assert result["start"].size == 0


def test_detect_validates_inputs():
    # Non-constant signal so the zero-variance early-exit doesn't intercept.
    rng = np.random.default_rng(7)
    sig = rng.standard_normal(2000)
    with pytest.raises(ValueError, match="signal must be 1D"):
        detect_oscillatory_events(
            sig.reshape(-1, 1),
            fs=1000.0,
            frequency_band=(40.0, 60.0),
            threshold_band=(1.0, np.inf),
            duration_band=(0.05, 1.0),
            min_interval=0.05,
        )
    with pytest.raises(ValueError, match="frequency_band"):
        detect_oscillatory_events(
            sig,
            fs=1000.0,
            frequency_band=(60.0, 40.0),
            threshold_band=(1.0, np.inf),
            duration_band=(0.05, 1.0),
            min_interval=0.05,
        )
    with pytest.raises(ValueError, match="threshold_band"):
        detect_oscillatory_events(
            sig,
            fs=1000.0,
            frequency_band=(40.0, 60.0),
            threshold_band=(2.0, 1.0),
            duration_band=(0.05, 1.0),
            min_interval=0.05,
        )
    with pytest.raises(ValueError, match="duration_band"):
        detect_oscillatory_events(
            sig,
            fs=1000.0,
            frequency_band=(40.0, 60.0),
            threshold_band=(1.0, np.inf),
            duration_band=(1.0, 0.5),
            min_interval=0.05,
        )


def test_detect_returns_empty_for_zero_variance_signal():
    sig = np.ones(2000)
    result = detect_oscillatory_events(
        sig,
        fs=1000.0,
        frequency_band=(40.0, 60.0),
        threshold_band=(1.0, np.inf),
        duration_band=(0.05, 1.0),
        min_interval=0.05,
    )
    assert result["start"].size == 0


def test_detect_respects_t_start_offset():
    fs = 1000.0
    sig = _signal_with_bursts(fs=fs, burst_times=(2.0,))
    result = detect_oscillatory_events(
        sig,
        fs=fs,
        frequency_band=(40.0, 60.0),
        threshold_band=(1.0, np.inf),
        duration_band=(0.05, 1.0),
        min_interval=0.05,
        t_start=100.0,
    )
    assert result["start"].size >= 1
    # detected start should be near 100 + 2 = 102s
    assert np.min(np.abs(result["start"] - 102.0)) < 0.05
