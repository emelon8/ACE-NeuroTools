"""Tests for aceneurotools.multimodal.event_correlograms."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aceneurotools.multimodal.event_correlograms import (
    _cross_correlogram,
    compute_autocorrelogram,
    compute_crosscorrelogram,
    compute_eventcorrelogram,
    compute_isi_distribution,
)


def _poisson_train(rate_hz: float, duration_s: float, seed: int) -> np.ndarray:
    """Homogeneous Poisson event times via exponential ISIs."""
    rng = np.random.default_rng(seed)
    n_expected = int(rate_hz * duration_s)
    isis = rng.exponential(1.0 / rate_hz, size=n_expected * 3)
    times = np.cumsum(isis)
    return times[times < duration_s]


# ---------------------------------------------------------------------------
# _cross_correlogram (numerical core)
# ---------------------------------------------------------------------------


def test_cross_correlogram_bin_centres_symmetric():
    t = np.array([1.0, 2.0, 3.0])
    _, B = _cross_correlogram(t, t, binsize=0.1, windowsize=0.5)
    # nbins should be odd and centred on 0
    assert len(B) % 2 == 1
    centre_idx = len(B) // 2
    assert B[centre_idx] == pytest.approx(0.0, abs=1e-9)


def test_cross_correlogram_self_zero_lag_peak():
    """Autocorrelogram of a regular train has a peak at the zero-lag bin."""
    t = np.arange(0.0, 10.0, 0.1)  # 10 Hz regular train
    C, B = _cross_correlogram(t, t, binsize=0.01, windowsize=0.05)
    centre = len(B) // 2
    # zero-lag bin contains every reference's own contribution → maximum
    assert C[centre] == max(C)


def test_cross_correlogram_poisson_flat_acg():
    """ACG of a Poisson train should be flat (≈ mean rate) at all non-trivial lags."""
    t = _poisson_train(rate_hz=50.0, duration_s=200.0, seed=42)
    C, B = _cross_correlogram(t, t, binsize=0.05, windowsize=1.0)
    # exclude the zero-lag bin (always elevated by the reference itself)
    centre = len(B) // 2
    mask = np.arange(len(B)) != centre
    mean_rate = len(t) / 200.0
    assert C[mask].mean() == pytest.approx(mean_rate, rel=0.1)


def test_cross_correlogram_empty_reference_returns_zeros():
    t1 = np.array([], dtype=np.float64)
    t2 = np.array([1.0, 2.0, 3.0])
    C, B = _cross_correlogram(t1, t2, binsize=0.1, windowsize=0.5)
    assert np.all(C == 0.0)
    assert len(B) == len(C)


def _cross_correlogram_reference(t1, t2, binsize, windowsize):
    """Faithful copy of the pre-vectorization triple-nested loop."""
    t1 = np.ascontiguousarray(t1, dtype=np.float64)
    t2 = np.ascontiguousarray(t2, dtype=np.float64)
    nbins = int((windowsize * 2) // binsize)
    if nbins % 2 == 0:
        nbins += 1
    w = (nbins / 2) * binsize
    C = np.zeros(nbins, dtype=np.float64)
    nt1, nt2 = t1.size, t2.size
    i2 = 0
    for i1 in range(nt1):
        lbound = t1[i1] - w
        while i2 < nt2 and t2[i2] < lbound:
            i2 += 1
        while i2 > 0 and t2[i2 - 1] > lbound:
            i2 -= 1
        rbound = lbound
        leftb = i2
        for j in range(nbins):
            k = 0
            rbound += binsize
            while leftb < nt2 and t2[leftb] < rbound:
                leftb += 1
                k += 1
            C[j] += k
    if nt1 > 0:
        C /= nt1 * binsize
    B = -w + binsize / 2 + np.arange(nbins) * binsize
    return C, B


@pytest.mark.parametrize("binsize,windowsize", [(0.05, 1.0), (0.01, 0.05), (0.1, 0.5), (0.02, 0.5)])
def test_cross_correlogram_matches_reference_loop(binsize, windowsize):
    """Vectorized implementation is bit-for-bit identical to the old loop."""
    for seed in range(6):
        t1 = _poisson_train(20.0, 60.0, seed)
        t2 = _poisson_train(25.0, 60.0, seed + 100)
        C_new, B_new = _cross_correlogram(t1, t2, binsize, windowsize)
        C_ref, B_ref = _cross_correlogram_reference(t1, t2, binsize, windowsize)
        np.testing.assert_array_equal(C_new, C_ref)
        np.testing.assert_allclose(B_new, B_ref)


def test_cross_correlogram_matches_reference_on_regular_train():
    """Boundary-heavy regular train (values on exact bin edges) still matches."""
    t = np.arange(0.0, 10.0, 0.1)
    C_new, _ = _cross_correlogram(t, t, 0.01, 0.05)
    C_ref, _ = _cross_correlogram_reference(t, t, 0.01, 0.05)
    np.testing.assert_array_equal(C_new, C_ref)


# ---------------------------------------------------------------------------
# compute_autocorrelogram
# ---------------------------------------------------------------------------


def test_compute_autocorrelogram_zero_bin_zeroed():
    group = {0: _poisson_train(20.0, 60.0, seed=1), 1: _poisson_train(20.0, 60.0, seed=2)}
    df = compute_autocorrelogram(group, binsize=0.01, windowsize=0.1, norm=True)
    # Zero-lag bin is explicitly zeroed per pynapple convention
    assert 0.0 in df.index
    assert (df.loc[0.0] == 0.0).all()


def test_compute_autocorrelogram_norm_baseline_one_for_poisson():
    group = {0: _poisson_train(30.0, 300.0, seed=3)}
    df = compute_autocorrelogram(group, binsize=0.02, windowsize=0.5, norm=True, t_start=0.0, t_end=300.0)
    nonzero = df.index != 0.0
    assert df[0][nonzero].mean() == pytest.approx(1.0, rel=0.15)


def test_compute_autocorrelogram_returns_dataframe():
    group = {0: np.array([1.0, 1.5, 2.0]), 1: np.array([0.5, 1.0])}
    df = compute_autocorrelogram(group, binsize=0.1, windowsize=0.5)
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) == {0, 1}


# ---------------------------------------------------------------------------
# compute_crosscorrelogram
# ---------------------------------------------------------------------------


def test_crosscorrelogram_single_dict_pairs():
    group = {
        0: _poisson_train(10.0, 50.0, seed=10),
        1: _poisson_train(10.0, 50.0, seed=11),
        2: _poisson_train(10.0, 50.0, seed=12),
    }
    df = compute_crosscorrelogram(group, binsize=0.05, windowsize=0.5)
    # 3 choose 2 = 3 pairs
    assert df.shape[1] == 3
    assert set(df.columns) == {(0, 1), (0, 2), (1, 2)}


def test_crosscorrelogram_two_dicts_full_product():
    g1 = {0: _poisson_train(10.0, 50.0, seed=20)}
    g2 = {10: _poisson_train(10.0, 50.0, seed=21), 11: _poisson_train(10.0, 50.0, seed=22)}
    df = compute_crosscorrelogram((g1, g2), binsize=0.05, windowsize=0.5)
    assert df.shape[1] == 2
    assert set(df.columns) == {(0, 10), (0, 11)}


def test_crosscorrelogram_reverse_flips_pairs():
    g = {0: np.array([1.0, 2.0]), 1: np.array([1.5, 2.5])}
    df_fwd = compute_crosscorrelogram(g, binsize=0.1, windowsize=0.5, reverse=False)
    df_rev = compute_crosscorrelogram(g, binsize=0.1, windowsize=0.5, reverse=True)
    assert list(df_fwd.columns) == [(0, 1)]
    assert list(df_rev.columns) == [(1, 0)]


# ---------------------------------------------------------------------------
# compute_eventcorrelogram
# ---------------------------------------------------------------------------


def test_eventcorrelogram_uniform_for_independent_trains():
    rng = np.random.default_rng(99)
    event = np.sort(rng.uniform(0, 200, size=400))
    group = {n: _poisson_train(15.0, 200.0, seed=100 + n) for n in range(3)}
    df = compute_eventcorrelogram(group, event, binsize=0.05, windowsize=1.0, t_start=0.0, t_end=200.0, norm=True)
    # Each column's mean should hover around 1.0 (normalized)
    for col in df.columns:
        assert df[col].mean() == pytest.approx(1.0, rel=0.2)


# ---------------------------------------------------------------------------
# compute_isi_distribution
# ---------------------------------------------------------------------------


def test_isi_distribution_ndarray_input_single_column():
    t = _poisson_train(20.0, 100.0, seed=7)
    df = compute_isi_distribution(t, bins=15)
    assert list(df.columns) == [0]
    assert df.shape[0] == 15
    # ISIs are nonnegative, so bin centres are nonnegative
    assert (df.index >= 0).all()


def test_isi_distribution_log_scale_finite():
    t = _poisson_train(20.0, 100.0, seed=8)
    df = compute_isi_distribution(t, bins=15, log_scale=True)
    assert np.all(np.isfinite(df.index))


def test_isi_distribution_array_bins_validated():
    t = np.array([0.0, 0.1, 0.3, 0.6])
    with pytest.raises(ValueError, match="monotonically"):
        compute_isi_distribution(t, bins=np.array([0.0, 0.5, 0.3]))


def test_isi_distribution_empty_train_handled():
    df = compute_isi_distribution({0: np.array([5.0])}, bins=5)
    assert df.shape == (5, 1)
    assert (df[0] == 0).all()


def test_isi_distribution_rejects_bad_type():
    with pytest.raises(TypeError):
        compute_isi_distribution("not an array", bins=10)
