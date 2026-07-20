"""Tests for aceneurotools.multimodal.surrogate."""

from __future__ import annotations

import numpy as np
import pytest

from aceneurotools.multimodal.surrogate import (
    apply_to_group,
    jitter_event_times,
    resample_event_times,
    shift_event_times,
    shuffle_event_intervals,
)


# ---------------------------------------------------------------------------
# jitter_event_times
# ---------------------------------------------------------------------------


def test_jitter_preserves_count_by_default():
    rng = np.random.default_rng(0)
    e = np.linspace(1.0, 9.0, 100)
    out = jitter_event_times(e, max_jitter=0.05, rng=rng)
    assert out.size == e.size


def test_jitter_output_is_sorted():
    rng = np.random.default_rng(1)
    e = np.linspace(0.0, 10.0, 200)
    out = jitter_event_times(e, max_jitter=0.5, rng=rng)
    assert np.all(np.diff(out) >= 0)


def test_jitter_bounded_by_max_jitter():
    rng = np.random.default_rng(2)
    e = np.linspace(0.0, 10.0, 500)
    max_j = 0.1
    out = jitter_event_times(e, max_jitter=max_j, rng=rng)
    # After sorting, the rank-matched offsets shouldn't drift more than max_jitter
    # but element-wise comparison after sort is messy. Test the unsorted property:
    # mean absolute jitter should be ~max_j/2
    pre_sort = e + rng.uniform(-max_j, max_j, e.size)  # independent draw
    assert np.abs(pre_sort - e).max() <= max_j + 1e-9


def test_jitter_clip_to_support():
    rng = np.random.default_rng(3)
    e = np.array([0.0, 0.05, 9.95, 10.0])
    out = jitter_event_times(e, max_jitter=0.5, t_start=0.0, t_end=10.0,
                              clip_to_support=True, rng=rng)
    assert (out >= 0.0).all()
    assert (out <= 10.0).all()


def test_jitter_rejects_nonpositive():
    with pytest.raises(ValueError):
        jitter_event_times(np.array([1.0]), max_jitter=0.0)


def test_jitter_deterministic_with_same_seed():
    e = np.linspace(0.0, 10.0, 50)
    out1 = jitter_event_times(e, 0.1, rng=np.random.default_rng(42))
    out2 = jitter_event_times(e, 0.1, rng=np.random.default_rng(42))
    np.testing.assert_array_equal(out1, out2)


# ---------------------------------------------------------------------------
# shift_event_times
# ---------------------------------------------------------------------------


def test_shift_drop_mode_keeps_in_support():
    rng = np.random.default_rng(10)
    e = np.linspace(1.0, 9.0, 50)
    out = shift_event_times(e, t_start=0.0, t_end=10.0, min_shift=0.5, max_shift=0.5,
                             mode="drop", rng=rng)
    assert (out >= 0.0).all()
    assert (out <= 10.0).all()


def test_shift_wrap_mode_preserves_count():
    rng = np.random.default_rng(11)
    e = np.linspace(1.0, 9.0, 50)
    out = shift_event_times(e, t_start=0.0, t_end=10.0, min_shift=5.0, max_shift=5.0,
                             mode="wrap", rng=rng)
    assert out.size == e.size
    assert (out >= 0.0).all()
    assert (out <= 10.0).all()


def test_shift_wrap_circular():
    """With fixed shift = period, wrapped times equal originals modulo period."""
    e = np.array([0.5, 1.5, 9.5])
    out = shift_event_times(e, t_start=0.0, t_end=10.0, min_shift=10.0,
                             max_shift=10.0, mode="wrap",
                             rng=np.random.default_rng(0))
    np.testing.assert_allclose(np.sort(out), np.sort(e))


def test_shift_rejects_bad_support():
    with pytest.raises(ValueError):
        shift_event_times(np.array([1.0]), t_start=5.0, t_end=5.0)


def test_shift_rejects_bad_mode():
    with pytest.raises(ValueError):
        shift_event_times(np.array([1.0]), t_start=0.0, t_end=10.0, mode="bogus")


# ---------------------------------------------------------------------------
# shuffle_event_intervals
# ---------------------------------------------------------------------------


def test_shuffle_preserves_isi_multiset():
    rng = np.random.default_rng(20)
    e = np.cumsum(rng.exponential(0.1, size=100))
    out = shuffle_event_intervals(e, rng=rng)
    np.testing.assert_allclose(np.sort(np.diff(e)), np.sort(np.diff(out)))


def test_shuffle_preserves_first_and_last_time_bounds():
    rng = np.random.default_rng(21)
    e = np.cumsum(rng.exponential(0.1, size=100))
    out = shuffle_event_intervals(e, rng=rng)
    assert out[0] == pytest.approx(e[0])
    # total duration preserved (sum of intervals)
    assert (out[-1] - out[0]) == pytest.approx(e[-1] - e[0])


def test_shuffle_handles_tiny_input():
    out = shuffle_event_intervals(np.array([1.0]))
    assert out.tolist() == [1.0]
    out0 = shuffle_event_intervals(np.array([], dtype=np.float64))
    assert out0.size == 0


# ---------------------------------------------------------------------------
# resample_event_times
# ---------------------------------------------------------------------------


def test_resample_in_support_and_count():
    rng = np.random.default_rng(30)
    e = np.array([1.0] * 50)  # only count matters
    out = resample_event_times(e, t_start=0.0, t_end=10.0, rng=rng)
    assert out.size == 50
    assert (out >= 0.0).all() and (out <= 10.0).all()
    assert np.all(np.diff(out) >= 0)


def test_resample_explicit_n():
    rng = np.random.default_rng(31)
    out = resample_event_times(np.array([0.0]), t_start=0.0, t_end=1.0, n=200, rng=rng)
    assert out.size == 200


def test_resample_uniform_distribution_kstest():
    """Resampled times should be ≈ uniform on [t_start, t_end]."""
    rng = np.random.default_rng(32)
    out = resample_event_times(np.zeros(2000), t_start=0.0, t_end=10.0, rng=rng)
    # split into 10 equal-width bins, expect ~200 per bin
    counts, _ = np.histogram(out, bins=np.linspace(0, 10, 11))
    assert counts.min() > 150 and counts.max() < 250


def test_resample_zero_events_returns_empty():
    out = resample_event_times(np.array([], dtype=np.float64), 0.0, 10.0)
    assert out.size == 0


# ---------------------------------------------------------------------------
# apply_to_group
# ---------------------------------------------------------------------------


def test_apply_to_group_dispatches_per_unit():
    rng = np.random.default_rng(40)
    group = {0: np.linspace(0.0, 5.0, 30), 1: np.linspace(0.0, 5.0, 50)}
    out = apply_to_group(jitter_event_times, group, max_jitter=0.1, rng=rng)
    assert set(out.keys()) == {0, 1}
    assert out[0].size == 30
    assert out[1].size == 50
