"""Known-signal checks for filtering, masks, normalization, and file loading."""

from __future__ import annotations

import numpy as np
import pytest

from aceneurotools.shared.file_io import load_obj
from aceneurotools.shared.signal_processing import filter_signal
from aceneurotools.stats.signal_utils import (
    compute_coherence,
    compute_cross_correlation,
    handle_nans,
    normalize_signals_global,
    slice_signal,
    trim_filter_edges,
)


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


def test_numpy_loader_disallows_pickled_object_arrays(tmp_path):
    path = tmp_path / "unsafe.npz"
    np.savez(path, payload=np.array([{"bad": "object"}], dtype=object))
    with load_obj(path) as archive, pytest.raises(ValueError, match="allow_pickle=False"):
        _ = archive["payload"]


@pytest.mark.parametrize("extension", ["pkl", "pickle", "npy", "txt"])
def test_loader_rejects_unapproved_formats_before_opening(tmp_path, extension):
    with pytest.raises(ValueError, match="unsupported"):
        load_obj(tmp_path / f"data.{extension}")


def test_numpy_and_hdf5_numeric_roundtrips(tmp_path):
    import h5py

    source = np.arange(12).reshape(3, 4)
    path = tmp_path / "safe.npz"
    np.savez(path, values=source)
    with load_obj(path) as archive:
        np.testing.assert_array_equal(archive["values"], source)
    path = tmp_path / "safe.h5"
    with h5py.File(path, "w") as handle:
        handle["values"] = source
    with load_obj(path) as handle:
        np.testing.assert_array_equal(handle["values"][:], source)
        assert handle.mode == "r"
