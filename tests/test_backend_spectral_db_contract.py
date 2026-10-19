"""dB conversion contract for spectral power: non-positive power is missing, not a floor.

``multitaper_spectrogram`` returns linear power.  Converting raw linear zeros to dB
must not manufacture a physical-looking ``-300 dB`` floor (as ``log10(power + 1e-30)``
does), and negative / ``±inf`` / NaN power must not poison band averages.  The
``power_to_db`` helper centralises this policy; these tests pin it down against
hand-written oracles and the existing shared conversion.
"""

from __future__ import annotations

import warnings

import matplotlib.pyplot as plt
import numpy as np
import pytest

from aceneurotools.multimodal.stats_config import StatsConfig
from aceneurotools.shared.multitaper_spectrogram_python import multitaper_spectrogram, nanpow2db
from aceneurotools.multimodal.coherence_analysis import CoherenceAnalysis
from aceneurotools.multimodal.signal_utils import compute_spectral_power, power_to_db


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


def _spectral_power_matrix(signal: np.ndarray, fr: float, time_bandwidth: float = 2.0):
    """Raw linear-power matrix computed with the exact options ``compute_spectral_power`` uses."""
    power_matrix, _times, frequencies = multitaper_spectrogram(
        np.asarray(signal),
        fr,
        frequency_range=[0.0, fr / 2],
        time_bandwidth=time_bandwidth,
        num_tapers=int(time_bandwidth * 2 - 1),
        window_params=[2.0, 1.0],
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
    return power_matrix, frequencies


def test_power_to_db_maps_non_positive_and_non_finite_power_to_missing():
    power = np.array([0.0, -1.0, 1e-12, 0.5, 1.0, 50.0, np.nan, np.inf, -np.inf])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with np.errstate(all="raise"):
            actual = power_to_db(power)

    expected = np.full(power.shape, np.nan)
    positive_finite = np.isfinite(power) & (power > 0)
    expected[positive_finite] = 10.0 * np.log10(power[positive_finite])
    np.testing.assert_array_equal(actual, expected)
    # Positive finite values are exactly the shared multitaper conversion.
    np.testing.assert_array_equal(actual[positive_finite], nanpow2db(power[positive_finite]))
    assert positive_finite.sum() == 4 and np.isnan(actual[~positive_finite]).all()

    # Scalar in, float out — same convention as nanpow2db.
    scalar = power_to_db(1.0)
    assert isinstance(scalar, float) and scalar == 0.0
    assert np.isnan(power_to_db(0.0))


def test_compute_spectral_power_matches_independent_nanmean_db_oracle():
    fr = 64.0
    rng = np.random.default_rng(2027)
    signal = np.concatenate([rng.normal(size=int(fr * 4)), np.zeros(int(fr * 4))])
    power_matrix, frequencies = _spectral_power_matrix(signal, fr)
    mask = (frequencies >= 5.0) & (frequencies <= 15.0)
    raw = power_matrix[mask].ravel()
    # The band deliberately mixes positive and exact-zero power bins.
    assert (raw > 0).any() and (raw == 0).any()

    expected = np.nanmean(np.array([10.0 * np.log10(p) if p > 0 else np.nan for p in raw]))
    actual = compute_spectral_power(signal, fr, [5.0, 15.0], window_length=2.0, window_step=1.0, time_bandwidth=2.0)
    assert actual == pytest.approx(expected, rel=1e-12)


def test_all_zero_signal_reports_nan_not_the_log_offset_floor():
    result = compute_spectral_power(
        np.zeros(int(64 * 8)), 64.0, [4.0, 12.0], window_length=2.0, window_step=1.0, time_bandwidth=2.0
    )
    assert np.isnan(result)


def test_fully_missing_band_is_nan_without_numpy_runtime_warnings():
    signal = np.full(int(64 * 8), np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with np.errstate(all="raise"):
            result = compute_spectral_power(
                signal, 64.0, [4.0, 12.0], window_length=2.0, window_step=1.0, time_bandwidth=2.0
            )
    assert np.isnan(result)


def test_positive_power_result_is_unchanged_from_legacy_offset_formula():
    fr = 64.0
    signal = np.random.default_rng(11).normal(size=int(fr * 12))
    power_matrix, frequencies = _spectral_power_matrix(signal, fr)
    mask = (frequencies >= 5.0) & (frequencies <= 15.0)
    raw = power_matrix[mask]
    assert (raw > 0).all()
    legacy = float(np.mean(10.0 * np.log10(raw + 1e-30)))
    actual = compute_spectral_power(signal, fr, [5.0, 15.0], window_length=2.0, window_step=1.0, time_bandwidth=2.0)
    # Not bit-identical to the legacy formula: the removed +1e-30 offset shifted
    # each bin by a relative ~1e-30 / (power * ln(10)), far below rtol=1e-9 here.
    assert actual == pytest.approx(legacy, rel=1e-9)


@pytest.mark.parametrize("signal_kind", ["all_zero", "part_zero"])
def test_spectrogram_plot_tolerates_zero_power_bins(tmp_path, signal_kind):
    fr = 64.0
    if signal_kind == "all_zero":
        signal = np.zeros(int(fr * 8))
    else:
        rng = np.random.default_rng(5)
        signal = np.concatenate([rng.normal(size=int(fr * 4)), np.zeros(int(fr * 4))])
    config = StatsConfig(
        headless=True,
        plot_formats=["png"],
        color_dpi=40,
        spectrogram_window_length=2,
        spectrogram_window_step=1,
        spectrogram_time_bandwidth=2,
        spectrogram_freq_lims=[0, 32],
    )
    CoherenceAnalysis(config)._plot_spectrogram(signal, fr, 7, "drug", {}, "EEG", tmp_path)
    assert len(list(tmp_path.glob("spectrogram_*.png"))) == 1
