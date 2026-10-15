"""Coherence and power against independent FFTs, known gains, and paired summaries."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from scipy.signal.windows import hann
from scipy.stats import wilcoxon

from aceneurotools.config.stats_config import StatsConfig
from aceneurotools.stats import coherence_analysis as module
from aceneurotools.stats.coherence_analysis import CoherenceAnalysis, SubjectCoherenceResult
from aceneurotools.stats.signal_utils import compute_coherence


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


@pytest.mark.parametrize("segment_seconds", [1, 2, 4])
def test_welch_coherence_matches_manual_averaged_cross_spectra(segment_seconds):
    rng = np.random.default_rng(83)
    x = rng.normal(size=4096)
    y = 0.7 * x + rng.normal(size=x.size)
    size = 64 * segment_seconds
    taper = hann(size, sym=False)
    transforms = []
    for signal in (x, y):
        windows = [signal[start : start + size] for start in range(0, signal.size - size + 1, size // 2)]
        transforms.append(np.fft.rfft([(window - window.mean()) * taper for window in windows], axis=1))
    fx, fy = transforms
    expected = np.abs(np.mean(fx.conj() * fy, axis=0)) ** 2 / (
        np.mean(np.abs(fx) ** 2, axis=0) * np.mean(np.abs(fy) ** 2, axis=0)
    )
    frequencies = np.fft.rfftfreq(size, d=1 / 64)
    band = (frequencies >= 4) & (frequencies <= 12)
    assert compute_coherence(x, y, 64, [4, 12], segment_seconds) == pytest.approx(expected[band].mean(), abs=1e-12)


def test_identical_signals_have_unit_coherence_and_empty_band_is_undefined():
    signal = np.random.default_rng(14).normal(size=4096)
    assert compute_coherence(signal, signal * 3, 64, [4, 12], 2) == pytest.approx(1)
    assert np.isnan(compute_coherence(signal, signal, 64, [40, 50], 2))


@pytest.mark.parametrize("plots", [False, True])
def test_actual_subject_analysis_tracks_known_amplitude_change_and_preserves_inputs(tmp_path, monkeypatch, plots):
    base = np.sin(2 * np.pi * 8 * np.arange(1024) / 64) + np.random.default_rng(8).normal(0, 0.01, 1024)
    x = np.r_[base, base * 2]
    y = x * 3
    before = x.copy(), y.copy()
    config = StatsConfig(
        lowcut=4,
        highcut=12,
        headless=True,
        plot_formats=["png"],
        color_dpi=40,
        spectrogram_window_length=2,
        spectrogram_window_step=1,
        spectrogram_freq_lims=[0, 32],
        coherence_nperseg_seconds=2,
    )
    monkeypatch.setattr(module, "_HAS_XRSCIPY", False)
    options = dict(
        signal_1=x,
        signal_2=y,
        fr=64,
        line_num=7,
        selections={7: [[0, 16 / 60], [16 / 60, 32 / 60]]},
        drug="control/drug",
        output_dir=tmp_path,
        signal_1_label="EEG",
        signal_2_label="Calcium",
        plot_spectrogram=plots,
        plot_signal_overview=plots,
        plot_coherogram=plots,
    )
    if plots:
        with pytest.warns(UserWarning, match="coherogram"):
            result = CoherenceAnalysis(config).run_subject(**options)
    else:
        result = CoherenceAnalysis(config).run_subject(**options)
    assert result.METRIC_NAMES == ["EEG Power", "Calcium Power", "Coherence", "XC", "Lag"]
    # PSD scales with amplitude squared; the logarithmic output shifts by 6.02 dB.
    np.testing.assert_allclose(
        np.array(result.treatment_stats[:2]) - result.control_stats[:2], 20 * np.log10(2), atol=1e-10
    )
    np.testing.assert_allclose(result.control_stats[2:], [1, 1, 0], atol=1e-10)
    np.testing.assert_allclose(result.treatment_stats[2:], [1, 1, 0], atol=1e-10)
    assert np.isnan(result.ratios[-1])
    np.testing.assert_array_equal(x, before[0])
    np.testing.assert_array_equal(y, before[1])
    if plots:
        assert len(list(tmp_path.glob("spectrogram_*.png"))) == 2
        assert len(list(tmp_path.glob("signal_*.png"))) == 2
        assert not list(tmp_path.glob("coherogram_*.png"))


def test_population_summary_preserves_subject_pairs_and_matches_wilcoxon(tmp_path):
    results = [
        SubjectCoherenceResult(i, "drug", [i, i * 2, 0.5, 0.8, 0], [i + 1, i * 2 + 1, 0.7, 0.9, 0.1], [1] * 5)
        for i in range(1, 5)
    ]
    results.append(SubjectCoherenceResult(99, "unrequested", [0] * 5, [0] * 5, [0] * 5))
    summary = CoherenceAnalysis().run_population(results, {"drug": [1, 2, 3, 4], "empty": []}, tmp_path, "EEG")
    assert set(summary) == {"drug"}
    frame = summary["drug"]
    power = frame.loc[frame["Measurement"] == "Signal 1 Power"].iloc[0]
    assert power[("Control", "mean")] == 2.5
    assert power[("Treatment", "mean")] == 3.5
    assert power[("Ratio", "mean")] == pytest.approx(3.5 / 2.5)
    assert power[("P-value", "")] == pytest.approx(wilcoxon([1, 2, 3, 4], [2, 3, 4, 5]).pvalue)
    lag = frame.loc[frame["Measurement"] == "Lag"].iloc[0]
    assert np.isnan(lag[("P-value", "")])
    raw = pd.read_csv(tmp_path / "drug_EEG_data.csv")
    assert raw.shape[0] == 20 and set(raw.line_num) == {1, 2, 3, 4}
    assert (tmp_path / "drug_EEG_avg_data.csv").is_file()


def test_population_zero_baseline_is_nan_and_small_group_has_no_invented_p_value():
    frame = pd.DataFrame(
        {"Measurement": ["Power"] * 2, "Control": [0.0, 0.0], "Treatment": [1.0, 2.0], "Ratio": [np.nan, np.nan]}
    )
    average = CoherenceAnalysis._compute_mean_std(frame)
    assert np.isnan(average[("Ratio", "mean")].iloc[0])
    result = CoherenceAnalysis._add_p_values(frame, average)
    assert np.isnan(result["P-value"].iloc[0])
    assert CoherenceAnalysis._compute_mean_std(pd.DataFrame()).empty
    assert CoherenceAnalysis._add_p_values(pd.DataFrame(), pd.DataFrame()).empty


def test_missing_selection_and_failed_plot_save_have_explicit_outcomes(tmp_path, monkeypatch):
    engine = CoherenceAnalysis(StatsConfig(headless=True, plot_formats=["png"]))
    engine._plot_signal_with_slices(np.arange(10), 10, 7, {}, "EEG", tmp_path, "drug")
    assert list(tmp_path.iterdir()) == []
    with pytest.warns(UserWarning, match="Spectrogram failed"):
        engine._plot_spectrogram(np.arange(10), 10, 7, "drug", {}, "EEG", tmp_path)
    fig = plt.figure()
    monkeypatch.setattr(fig, "savefig", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.warns(UserWarning, match="Could not save"):
        module._save_figure(fig, tmp_path / "plot.tiff", 40)
