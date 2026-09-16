"""Tests for aceneurotools.stats.perievent."""

from __future__ import annotations

import numpy as np
import pytest

from aceneurotools.stats.perievent import (
    _normalize_window,
    compute_event_triggered_average,
    compute_perievent,
    compute_spike_triggered_average,
)

# ---------------------------------------------------------------------------
# window normalization
# ---------------------------------------------------------------------------


def test_normalize_window_scalar():
    assert _normalize_window(0.5) == (0.5, 0.5)


def test_normalize_window_tuple_signs_absorbed():
    assert _normalize_window((-0.5, 1.0)) == (0.5, 1.0)
    assert _normalize_window((0.5, 1.0)) == (0.5, 1.0)


def test_normalize_window_rejects_zero():
    with pytest.raises(ValueError):
        _normalize_window(0)
    with pytest.raises(ValueError):
        _normalize_window((0, 0))


def test_normalize_window_rejects_bad_type():
    with pytest.raises(TypeError):
        _normalize_window("0.5")


# ---------------------------------------------------------------------------
# compute_perievent
# ---------------------------------------------------------------------------


def test_perievent_drops_boundary_events_by_default():
    fs = 100.0
    sig = np.arange(1000, dtype=np.float64)
    events = np.array([0.0, 1.0, 5.0, 9.99])  # first and last too close to edges
    out = compute_perievent(sig, events, fs=fs, window=0.5)
    # Need 50 samples before and 50 after. Only event at 1.0s (idx=100), 5.0s
    # (idx=500) fit.
    assert out["n_events"] == 2
    assert out["matrix"].shape == (2, 101)


def test_perievent_keeps_all_with_nan_padding():
    fs = 100.0
    sig = np.arange(1000, dtype=np.float64)
    events = np.array([0.0, 5.0, 9.99])
    out = compute_perievent(sig, events, fs=fs, window=0.5,
                            drop_boundary_events=False)
    assert out["n_events"] == 3
    # First event at t=0 should have NaNs in the "before" half
    assert np.any(np.isnan(out["matrix"][0, :50]))


def test_perievent_time_axis_symmetric():
    out = compute_perievent(np.arange(1000, dtype=np.float64),
                            np.array([5.0]), fs=100.0, window=0.3)
    assert out["time"][0] == pytest.approx(-0.3)
    assert out["time"][-1] == pytest.approx(0.3)
    assert out["time"][len(out["time"]) // 2] == pytest.approx(0.0)


def test_perievent_asymmetric_window():
    out = compute_perievent(np.arange(1000, dtype=np.float64),
                            np.array([5.0]), fs=100.0, window=(0.2, 0.5))
    # 20 + 50 + 1 = 71 samples
    assert out["matrix"].shape == (1, 71)
    assert out["time"][0] == pytest.approx(-0.2)
    assert out["time"][-1] == pytest.approx(0.5)


def test_perievent_event_index_correct():
    fs = 100.0
    sig = np.arange(1000, dtype=np.float64)
    out = compute_perievent(sig, np.array([5.0]), fs=fs, window=0.1)
    # Event at sample 500. Window of 0.1s = 10 samples each side.
    # Slice is [490:511], centred on 500. So matrix[0, 10] should be 500.
    assert out["matrix"][0, 10] == 500.0


def test_perievent_empty_events_returns_empty_matrix():
    out = compute_perievent(np.arange(1000.0), np.array([]),
                            fs=100.0, window=0.5)
    assert out["n_events"] == 0
    assert out["matrix"].shape == (0, 101)
    assert out["time"].shape == (101,)


def test_perievent_t_start_offset():
    fs = 100.0
    sig = np.arange(1000, dtype=np.float64)
    # signal starts at absolute time 50s; event at t=55s should map to sample 500.
    out = compute_perievent(sig, np.array([55.0]), fs=fs, window=0.1,
                            t_start=50.0)
    assert out["n_events"] == 1
    assert out["matrix"][0, 10] == 500.0


def test_perievent_rejects_non_1d_signal():
    with pytest.raises(ValueError, match="1D"):
        compute_perievent(np.zeros((10, 10)), np.array([1.0]), fs=100.0, window=0.5)


# ---------------------------------------------------------------------------
# compute_event_triggered_average
# ---------------------------------------------------------------------------


def test_eta_recovers_known_waveform():
    """ETA of a clean signal aligned to a known waveform should recover it."""
    fs = 1000.0
    n_samples = 5 * int(fs)
    t = np.arange(n_samples) / fs
    sig = np.zeros(n_samples)
    # Inject a 50 Hz cosine burst of length 0.2s at 8 event times
    event_times = np.array([0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0])
    burst_len = int(0.2 * fs)
    for et in event_times:
        i0 = int(et * fs)
        burst = np.cos(2 * np.pi * 50.0 * np.arange(burst_len) / fs)
        sig[i0: i0 + burst_len] += burst

    out = compute_event_triggered_average(sig, event_times, fs=fs, window=(0.0, 0.2))
    # Mean at t=0 should be ~1 (cosine starts at 1)
    assert out["mean"][0] == pytest.approx(1.0, abs=0.05)
    # SEM should be very small (deterministic injection)
    assert out["sem"].max() < 1e-9
    assert out["n_events"] == 8


def test_eta_returns_zero_signal_for_no_events():
    out = compute_event_triggered_average(np.arange(1000.0), np.array([]),
                                          fs=100.0, window=0.5)
    assert out["n_events"] == 0
    assert out["mean"].shape == (101,)
    assert np.all(out["mean"] == 0)


def test_eta_keys_consistent():
    fs = 100.0
    sig = np.random.default_rng(0).standard_normal(1000)
    events = np.array([3.0, 5.0, 7.0])
    out = compute_event_triggered_average(sig, events, fs=fs, window=0.5)
    for key in ("time", "mean", "sem", "std", "matrix", "n_events"):
        assert key in out
    assert out["matrix"].shape == (3, 101)
    assert out["mean"].shape == (101,)


def test_eta_sem_decreases_with_more_events():
    fs = 100.0
    rng = np.random.default_rng(1)
    sig = rng.standard_normal(10000)
    few_events = rng.uniform(2.0, 98.0, size=10)
    many_events = rng.uniform(2.0, 98.0, size=200)
    out_few = compute_event_triggered_average(sig, few_events, fs=fs, window=0.5)
    out_many = compute_event_triggered_average(sig, many_events, fs=fs, window=0.5)
    # SEM ~ std/sqrt(n) so should shrink with more events
    assert out_many["sem"].mean() < out_few["sem"].mean()


def test_eta_handles_partial_events_with_nan_padding():
    fs = 100.0
    sig = np.ones(1000)
    # Event at t=9.99s — most of the +window slice is past the end
    events = np.array([5.0, 9.99])
    out = compute_event_triggered_average(sig, events, fs=fs, window=0.5,
                                          drop_boundary_events=False)
    # With nanmean, mean is still well-defined where at least one event
    # contributed
    assert np.all(np.isfinite(out["mean"]))


# ---------------------------------------------------------------------------
# compute_spike_triggered_average
# ---------------------------------------------------------------------------


def test_sta_is_alias_for_eta():
    fs = 100.0
    sig = np.random.default_rng(0).standard_normal(1000)
    events = np.array([3.0, 5.0, 7.0])
    eta = compute_event_triggered_average(sig, events, fs=fs, window=0.5)
    sta = compute_spike_triggered_average(sig, events, fs=fs, window=0.5)
    np.testing.assert_array_equal(eta["mean"], sta["mean"])
    np.testing.assert_array_equal(eta["matrix"], sta["matrix"])
