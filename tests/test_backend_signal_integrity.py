"""Known-signal checks for filtering, masks, normalization, and file loading."""

from __future__ import annotations

import numpy as np
import pytest

from aceneurotools.multimodal.signal_utils import (
    compute_coherence,
    compute_cross_correlation,
    handle_nans,
    mask_filter_transients,
    normalize_signals_global,
    slice_signal,
    trim_filter_edges,
)
from aceneurotools.shared.signal_processing import filter_signal


@pytest.mark.parametrize("family,order", [("butter", 4), ("BUTTERWORTH", 4), ("fir", 81)])
def test_filter_preserves_in_band_amplitude_and_rejects_out_of_band_without_mutation(family, order):
    fs = 100
    time = np.arange(2000) / fs
    desired = np.sin(2 * np.pi * 5 * time)
    nuisance = np.sin(2 * np.pi * 25 * time)
    signal = desired + nuisance
    before = signal.copy()
    result = filter_signal(signal, order, [3, 8], family, "bandpass", fs)
    interior = slice(300, -300)
    assert result.shape == signal.shape
    # Projection against known orthogonal tones measures amplitude, independent
    # of the implementation's coefficients or choice of filtering routine.
    assert 2 * np.mean(result[interior] * desired[interior]) == pytest.approx(1, abs=0.08)
    assert abs(2 * np.mean(result[interior] * nuisance[interior])) < 0.02
    np.testing.assert_array_equal(signal, before)


def test_nan_gaps_at_limit_interpolate_and_long_gaps_are_masked():
    source = np.array([0, np.nan, np.nan, 3, np.nan, np.nan, np.nan, 7.0])
    before = source.copy()
    cleaned, mask = handle_nans(source, fr=10, max_gap_seconds=0.2)
    np.testing.assert_array_equal(cleaned, [0, 1, 2, 3, 0, 0, 0, 7])
    np.testing.assert_array_equal(mask, [True, True, True, True, False, False, False, True])
    np.testing.assert_equal(source, before)


def test_all_missing_and_empty_signals_do_not_invent_valid_samples():
    cleaned, mask = handle_nans(np.full(8, np.nan), fr=10, max_gap_seconds=0.2)
    assert np.isfinite(cleaned).all()
    assert not mask.any()
    cleaned, mask = handle_nans(np.array([]), 10)
    assert cleaned.size == mask.size == 0


@pytest.mark.parametrize(
    "mask,margin,expected",
    [
        # gap at the start: margin clipped at the left boundary
        ([0, 0, 1, 1, 1, 1, 1, 1], 2, [0, 0, 0, 0, 1, 1, 1, 1]),
        # gap in the middle: margin added on both sides
        ([1, 1, 0, 1, 1, 1, 1], 1, [1, 0, 0, 0, 1, 1, 1]),
        # gap at the end: margin clipped at the right boundary
        ([1, 1, 1, 1, 0, 0], 2, [1, 1, 0, 0, 0, 0]),
        # two disjoint gaps keep one valid run between them
        ([1, 0, 0, 1, 1, 1, 1, 1, 0, 0, 1], 1, [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0]),
        # two close gaps merge once margins overlap
        ([1, 0, 0, 1, 1, 0, 1], 1, [0, 0, 0, 0, 0, 0, 0]),
        # a short valid run between adjacent gaps becomes fully masked
        ([1, 0, 1, 0, 1], 1, [0, 0, 0, 0, 0]),
        # non-positive margin returns an unchanged copy
        ([1, 0, 1], 0, [1, 0, 1]),
        # margin longer than the array: everything becomes masked
        ([1, 0, 1], 5, [0, 0, 0]),
        # all-False and all-True are fixed points
        ([0, 0, 0], 2, [0, 0, 0]),
        ([1, 1, 1], 2, [1, 1, 1]),
        # empty mask
        ([], 3, []),
    ],
)
def test_mask_filter_transients_extends_excluded_runs_with_clipping(mask, margin, expected):
    actual = mask_filter_transients(np.array(mask, dtype=bool), margin)
    np.testing.assert_array_equal(actual, np.array(expected, dtype=bool))


def test_mask_filter_transients_returns_a_copy_and_never_mutates_input():
    source = np.array([1, 0, 1], dtype=bool)
    before = source.copy()
    result = mask_filter_transients(source, 1)
    assert result is not source
    np.testing.assert_array_equal(source, before)
    result[0] = False
    np.testing.assert_array_equal(source, before)


def test_gap_adjacent_filter_transients_cannot_shift_pooled_normalization_parameters():
    """Margin samples are masked before normalization, so arbitrary filter
    residue around a long gap cannot move the pooled z-score parameters.
    Under the old exact-gap mask those samples leaked into mean/std."""
    fr = 20
    time = np.arange(240) / fr
    signal = np.sin(2 * np.pi * 2 * time) + 0.3 * np.sin(2 * np.pi * 7 * time)
    signal[100:140] = np.nan
    cleaned, valid = handle_nans(signal, fr, max_gap_seconds=0.5)
    margin = 10

    extended = mask_filter_transients(valid, margin)
    # Independent oracle mask: the excluded run [100, 140) ± margin.
    oracle = valid.copy()
    oracle[100 - margin : 140 + margin] = False
    np.testing.assert_array_equal(extended, oracle)

    # Extreme values stand in for whatever transient the filter leaves in the
    # margin; a correct mask makes the normalization parameters invariant.
    junk = cleaned.copy()
    junk[valid & ~extended] = 1e6
    masked_clean = cleaned.copy()
    masked_clean[~extended] = np.nan
    masked_junk = junk.copy()
    masked_junk[~extended] = np.nan
    params_clean = normalize_signals_global(masked_clean, masked_clean, masked_clean, masked_clean)[4]
    params_junk = normalize_signals_global(masked_junk, masked_junk, masked_junk, masked_junk)[4]
    assert params_junk == params_clean

    # Old behavior: mask only the exact gap samples, leaving the margin visible.
    old = junk.copy()
    old[~valid] = np.nan
    params_old = normalize_signals_global(old, old, old, old)[4]
    assert params_old["signal_1_std"] != pytest.approx(params_clean["signal_1_std"], rel=1e-3)


def test_global_normalization_uses_pooled_scale_and_retains_parameters():
    control = np.array([1.0, 2])
    treatment = np.array([5.0, 8])
    pooled = np.concatenate([control, treatment])
    one, two, three, four, params = normalize_signals_global(control, treatment, control * 2, treatment * 2)
    expected = (pooled - pooled.mean()) / pooled.std()
    np.testing.assert_allclose(np.concatenate([one, two]), expected)
    np.testing.assert_allclose(np.concatenate([three, four]), expected)
    assert params["signal_1_mean"] == pooled.mean()
    assert params["signal_1_std"] == pooled.std()
    np.testing.assert_array_equal(control, [1, 2])


def test_constant_normalization_is_finite_zero():
    results = normalize_signals_global(*(np.ones(4) for _ in range(4)))
    for signal in results[:4]:
        np.testing.assert_array_equal(signal, np.zeros(4))


def test_constant_normalization_preserves_missing_sample_masks():
    signal = np.array([1.0, np.nan, 1.0])
    results = normalize_signals_global(signal, signal, signal, signal)
    for normalized in results[:4]:
        np.testing.assert_equal(normalized, [0.0, np.nan, 0.0])


def test_slicing_uses_minutes_exclusive_end_and_clamps_only_recording_end():
    control, treatment = slice_signal(np.arange(120), {7: [[0.25, 0.5], [0.75, 10]]}, 7, fr=2)
    np.testing.assert_array_equal(control, np.arange(30, 60))
    np.testing.assert_array_equal(treatment, np.arange(90, 120))
    with pytest.raises(KeyError, match="line_num 99"):
        slice_signal(np.arange(120), {}, 99, 2)


def test_edge_trimming_warns_instead_of_returning_empty_data():
    source = np.arange(10.0)
    with pytest.warns(UserWarning, match="skipping trim"):
        np.testing.assert_array_equal(trim_filter_edges(source, 10, 1), source)
    np.testing.assert_array_equal(trim_filter_edges(source, 1, 2), source[2:-2])
    np.testing.assert_array_equal(trim_filter_edges(source, 1, 0), source)


def test_identical_signal_coherence_and_known_positive_delay():
    source = np.random.default_rng(8).normal(size=2048)
    assert compute_coherence(source, source, 100, [2, 20], nperseg_seconds=2) == pytest.approx(1)
    delayed = np.r_[np.zeros(7), source[:-7]]
    correlation, lag = compute_cross_correlation(source, delayed, 100, max_lag_seconds=0.2)
    assert correlation > 0.98
    assert lag == pytest.approx(0.07)


@pytest.mark.parametrize("values,expected", [
    ([np.nan, np.nan, 6.0, 9.0], [6.0, 6.0, 6.0, 9.0]),
    ([6.0, 9.0, np.nan, np.nan], [6.0, 9.0, 9.0, 9.0]),
])
def test_short_boundary_gaps_extend_nearest_acquired_value(values, expected):
    source = np.array(values)
    before = source.copy()
    cleaned, valid = handle_nans(source, fr=10, max_gap_seconds=0.2)
    np.testing.assert_array_equal(cleaned, expected)
    assert valid.all()
    np.testing.assert_equal(source, before)


def test_short_all_missing_signal_has_no_valid_sample():
    cleaned, valid = handle_nans(np.array([np.nan]), 10)
    assert not valid.any()
    assert np.isfinite(cleaned).all()
