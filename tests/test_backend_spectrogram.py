"""Multitaper PSD checked against SciPy periodograms and known signal energy."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pytest
from scipy.signal import detrend, periodogram
from scipy.signal.windows import dpss

from aceneurotools.shared.multitaper_spectrogram_python import (
    is_outlier,
    multitaper_spectrogram,
    nanpow2db,
)


def spectrum(data, **options):
    defaults = {"fs": 64, "time_bandwidth": 2, "window_params": [2, 1], "plot_on": False, "verbose": False}
    defaults.update(options)
    return multitaper_spectrogram(np.asarray(data), **defaults)


@pytest.mark.parametrize("weighting", ["unity", "eigen"])
@pytest.mark.parametrize("trend", ["constant", "linear", "off"])
@pytest.mark.parametrize("band", [None, [4, 20]])
def test_multitaper_matches_independent_periodograms(weighting, trend, band):
    data = np.random.default_rng(11).normal(size=384) + np.arange(384) / 100
    before = data.copy()
    actual, times, frequencies = spectrum(data, weighting=weighting, detrend_opt=trend, frequency_range=band)
    tapers, eigen = dpss(128, 2, Kmax=3, return_ratios=True)
    columns = []
    for start in range(0, len(data) - 128 + 1, 64):
        window = data[start : start + 128]
        if trend != "off":
            window = detrend(window, type=trend)
        spectra = []
        for taper in tapers:
            freqs, psd = periodogram(window, fs=64, window=taper, nfft=128, detrend=False, scaling="density")
            spectra.append(psd)
        columns.append(np.average(spectra, axis=0, weights=eigen if weighting == "eigen" else None))
    expected = np.stack(columns, axis=1)
    mask = np.ones(freqs.size, dtype=bool) if band is None else (freqs >= band[0]) & (freqs <= band[1])
    np.testing.assert_allclose(actual, expected[mask], rtol=1e-12, atol=1e-12)
    np.testing.assert_array_equal(frequencies, freqs[mask])
    np.testing.assert_array_equal(times, [1, 2, 3, 4, 5])
    np.testing.assert_array_equal(data, before)


@pytest.mark.parametrize("weighting", ["unity", "eigen", "adapt"])
def test_power_scales_quadratically_and_detects_tone(weighting):
    time = np.arange(512) / 64
    data = np.sin(2 * np.pi * 8 * time)
    psd, times, freqs = spectrum(data, weighting=weighting, detrend_opt="off")
    scaled, _, _ = spectrum(3 * data, weighting=weighting, detrend_opt="off")
    np.testing.assert_allclose(scaled, 9 * psd, rtol=1e-10, atol=1e-12)
    assert abs(freqs[np.argmax(psd.mean(axis=1))] - 8) <= 1
    assert np.isfinite(psd).all() and np.all(psd >= 0)
    assert times.size == psd.shape[1]


@pytest.mark.parametrize("kind", ["dc", "nyquist", "tone"])
def test_one_sided_psd_conserves_known_energy(kind):
    time = np.arange(384) / 64
    data = {"dc": np.ones(384), "nyquist": (-1.0) ** np.arange(384), "tone": np.sqrt(2) * np.sin(2 * np.pi * 8 * time)}[
        kind
    ]
    psd, _, frequencies = spectrum(data, detrend_opt="off")
    energy = psd.sum(axis=0) * (frequencies[1] - frequencies[0])
    np.testing.assert_allclose(energy, 1, atol=0.01)


def test_serial_and_parallel_results_and_transpose_agree():
    data = np.random.default_rng(3).normal(size=256)
    serial, times, freqs = spectrum(data)
    parallel, ptimes, pfreqs = spectrum(data, multiprocess=True, n_jobs=2)
    flipped, ftimes, ffreqs = spectrum(data, xyflip=True, min_nfft=256)
    np.testing.assert_array_equal(parallel, serial)
    np.testing.assert_array_equal(ptimes, times)
    np.testing.assert_array_equal(pfreqs, freqs)
    padded, _, _ = spectrum(data, min_nfft=256)
    np.testing.assert_array_equal(flipped, padded.T)
    np.testing.assert_array_equal(ftimes, times)
    assert ffreqs.size == 129


def test_zero_and_missing_windows_are_explicit():
    data = np.zeros(256)
    psd, _, _ = spectrum(data)
    np.testing.assert_array_equal(psd, 0)
    data[20] = np.nan
    psd, _, _ = spectrum(data)
    assert np.isnan(psd[:, 0]).all()
    np.testing.assert_array_equal(psd[:, 1:], 0)


def test_nyquist_clamping_does_not_mutate_caller_configuration():
    band = [0, 100]
    with pytest.warns(UserWarning, match="Nyquist"):
        _, _, freqs = spectrum(np.ones(256), frequency_range=band)
    assert freqs[-1] == 32
    assert band == [0, 100]


@pytest.mark.parametrize(
    "options",
    [
        {"weighting": "typo"},
        {"window_params": [0, 1]},
        {"window_params": [2, 0]},
        {"window_params": [2, 0.001]},
        {"time_bandwidth": float("nan")},
        {"num_tapers": 0},
        {"num_tapers": 1.5},
        {"min_nfft": -1},
        {"frequency_range": [10, 2]},
        {"frequency_range": [-1, 20]},
        {"frequency_range": [0, float("nan")]},
    ],
)
def test_invalid_spectral_settings_fail_clearly(options):
    defaults = {"fs": 64, "time_bandwidth": 2, "window_params": [2, 1], "plot_on": False, "verbose": False}
    defaults.update(options)
    with pytest.raises(ValueError):
        multitaper_spectrogram(np.ones(256), **defaults)


@pytest.mark.parametrize("fs", [0, -1, float("nan"), float("inf"), True])
def test_invalid_sampling_rates_are_rejected(fs):
    with pytest.raises(ValueError, match="fs"):
        multitaper_spectrogram(np.ones(256), fs, plot_on=False, verbose=False)


@pytest.mark.parametrize("shape", [(256, 1), (1, 256)])
def test_vector_shaped_inputs_match_one_dimensional_signal(shape):
    data = np.arange(256.0)
    expected, _, _ = spectrum(data)
    actual, _, _ = spectrum(data.reshape(shape))
    np.testing.assert_array_equal(actual, expected)


def test_rounding_default_windows_and_bad_input_dimensions():
    with pytest.warns(UserWarning, match="not divisible"):
        psd, times, _ = spectrum(np.ones(256), window_params=[2.01, 1.01])
    assert psd.shape[1] == times.size
    psd, _, _ = multitaper_spectrogram(np.ones(400), fs=64, plot_on=False, verbose=False)
    assert psd.shape[1] == 2
    with pytest.raises(TypeError, match="dimensions"):
        spectrum(np.ones((3, 4)))
    with pytest.raises(ValueError, match="shorter"):
        spectrum(np.ones(10))


@pytest.mark.parametrize("data,band", [(np.ones(128), [0, 32]), (np.ones(256), [0, 0])])
def test_plotting_handles_single_window_or_single_frequency(data, band):
    fig = None
    try:
        psd, times, freqs, (fig, ax) = multitaper_spectrogram(
            data,
            fs=64,
            frequency_range=band,
            time_bandwidth=2,
            window_params=[2, 1],
            plot_on=True,
            return_fig=True,
            verbose=True,
        )
        assert fig is not None
        assert ax.images[0].get_array().shape == psd.shape
        assert psd.shape == (freqs.size, times.size)
    finally:
        if fig is not None:
            plt.close(fig)


@pytest.mark.parametrize("data", [0, -1, [0, -1, 1, 10], np.array([0, -1, 1, 10])])
def test_power_to_db_handles_nonpositive_values_without_warnings_or_mutation(data):
    original = np.asarray(data).copy()
    with np.errstate(all="raise"):
        actual = nanpow2db(data)
    expected = np.full(original.shape, np.nan, dtype=float)
    valid = original > 0
    expected[valid] = 10 * np.log10(original[valid])
    np.testing.assert_equal(actual, expected)
    np.testing.assert_array_equal(np.asarray(data), original)


def test_outlier_detection_still_identifies_finite_outliers_with_missing_samples():
    actual = is_outlier(np.array([0, 0, 0, 0, 100, np.nan, np.inf]))
    np.testing.assert_array_equal(actual, [False, False, False, False, True, True, True])
