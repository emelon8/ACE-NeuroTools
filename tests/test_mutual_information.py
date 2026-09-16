"""Tests for compute_mutual_information in signal_utils."""

from __future__ import annotations

import math

import numpy as np
import pytest

from aceneurotools.stats.signal_utils import compute_mutual_information


def test_uniform_tuning_yields_zero_mi():
    """A flat rate across all bins is zero-informative."""
    tc = np.full(10, 5.0)
    occ = np.ones(10) / 10
    bps_sec, bps_spk = compute_mutual_information(tc, occ)
    assert bps_sec == pytest.approx(0.0)
    assert bps_spk == pytest.approx(0.0)


def test_perfect_tuning_yields_log2_n_per_spike():
    """A delta tuning curve over N equiprobable bins encodes log2(N) bits/spike."""
    n_bins = 8
    tc = np.zeros(n_bins)
    tc[3] = 10.0
    occ = np.full(n_bins, 1.0 / n_bins)
    bps_sec, bps_spk = compute_mutual_information(tc, occ)
    # mean_rate = (1/N) * 10 = 1.25; bits/sec = (1/N) * 10 * log2(10/1.25) = 1.25 * log2(8) = 1.25 * 3
    assert bps_sec == pytest.approx(1.25 * math.log2(n_bins))
    # bits/spike = bits/sec / mean_rate = 3.0 = log2(N)
    assert bps_spk == pytest.approx(math.log2(n_bins))


def test_mi_invariant_under_occupancy_scaling():
    """MI should not depend on whether occupancy is provided as counts or probs."""
    rng = np.random.default_rng(0)
    tc = rng.uniform(0, 10, size=20)
    occ_counts = rng.integers(1, 100, size=20).astype(float)
    occ_probs = occ_counts / occ_counts.sum()
    bps_sec_a, bps_spk_a = compute_mutual_information(tc, occ_counts)
    bps_sec_b, bps_spk_b = compute_mutual_information(tc, occ_probs)
    assert bps_sec_a == pytest.approx(bps_sec_b)
    assert bps_spk_a == pytest.approx(bps_spk_b)


def test_explicit_mean_rate_used_when_provided():
    tc = np.array([1.0, 9.0])
    occ = np.array([0.5, 0.5])
    # Override mean_rate
    bps_sec_default, _ = compute_mutual_information(tc, occ)
    bps_sec_override, _ = compute_mutual_information(tc, occ, mean_rate=5.0)
    # Default mean is also 5.0 here so values should match
    assert bps_sec_default == pytest.approx(bps_sec_override)


def test_zero_rate_returns_zero_and_nan():
    tc = np.zeros(5)
    occ = np.ones(5)
    bps_sec, bps_spk = compute_mutual_information(tc, occ)
    assert bps_sec == 0.0
    assert math.isnan(bps_spk)


def test_zero_occupancy_returns_zero_and_nan():
    tc = np.array([1.0, 2.0])
    occ = np.zeros(2)
    bps_sec, bps_spk = compute_mutual_information(tc, occ)
    assert bps_sec == 0.0
    assert math.isnan(bps_spk)


def test_empty_inputs_safe():
    bps_sec, bps_spk = compute_mutual_information(np.array([]), np.array([]))
    assert bps_sec == 0.0
    assert math.isnan(bps_spk)


def test_shape_mismatch_raises():
    with pytest.raises(ValueError, match="same shape"):
        compute_mutual_information(np.array([1.0, 2.0]), np.array([1.0]))


def test_mi_nonnegative_for_random_inputs():
    rng = np.random.default_rng(42)
    for _ in range(10):
        tc = rng.uniform(0, 10, size=15)
        occ = rng.uniform(0.1, 1.0, size=15)
        bps_sec, _ = compute_mutual_information(tc, occ)
        assert bps_sec >= -1e-12  # numerically nonnegative
