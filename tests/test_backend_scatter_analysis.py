"""Known-answer correlations, uncertainty, paired subjects, and gap masks."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pytest
from scipy.stats import norm, t, ttest_rel, wilcoxon

from aceneurotools.config.stats_config import StatsConfig
from aceneurotools.stats import scatter_analysis as scatter


@pytest.fixture(autouse=True)
def clean_figures_and_random_state():
    state = np.random.get_state()
    yield
    np.random.set_state(state)
    plt.close("all")


@pytest.mark.parametrize("corrected", [False, True])
def test_correlation_regression_and_significance_match_independent_equations(monkeypatch, corrected):
    x = np.linspace(-2, 2, 100)
    y = 3 * x + 7 + np.random.default_rng(2).normal(size=x.size)
    monkeypatch.setattr(scatter, "_HAS_STATSMODELS", False)
    xc, yc = x - x.mean(), y - y.mean()
    r = np.dot(xc, yc) / np.sqrt(np.dot(xc, xc) * np.dot(yc, yc))
    slope = np.dot(xc, yc) / np.dot(xc, xc)
    result = scatter.compute_statistics_robust(x, y, correct_autocorrelation=corrected)
    assert result["r"] == pytest.approx(r)
    assert result["slope"] == pytest.approx(slope)
    assert result["intercept"] == pytest.approx(y.mean() - slope * x.mean())
    assert result["n"] == result["n_effective"] == 100
    expected_p = 2 * t.sf(abs(r * np.sqrt(98 / (1 - r * r))), 98)
    assert result["p_value"] == pytest.approx(expected_p, rel=1e-10)
    assert result["p_value_corrected"] == pytest.approx(expected_p, rel=1e-7)


@pytest.mark.parametrize("r,n,confidence", [(0.5, 100, 0.95), (-0.3, 20, 0.99), (0, 12, 0.9)])
def test_fisher_interval_matches_normal_quantiles(r, n, confidence):
    critical = norm.ppf((1 + confidence) / 2) / np.sqrt(n - 3)
    expected = np.tanh([np.arctanh(r) - critical, np.arctanh(r) + critical])
    np.testing.assert_allclose(scatter.compute_confidence_interval(r, n, confidence), expected)


@pytest.mark.parametrize("r,n", [(1, 10), (-1, 10), (np.nan, 10), (0.5, 3)])
def test_undefined_fisher_intervals_remain_undefined(r, n):
    assert np.isnan(scatter.compute_confidence_interval(r, n)).all()


@pytest.mark.parametrize("values", [np.full(12, np.nan), np.ones(12), np.arange(9.0)])
def test_insufficient_or_constant_samples_do_not_invent_a_regression(values):
    with np.errstate(all="raise"):
        result = scatter.compute_statistics_robust(values, np.arange(values.size, dtype=float))
    assert np.isnan(result["r"]) and np.isnan(result["slope"])


def test_pairwise_missing_samples_are_excluded_without_mutating_inputs():
    x = np.arange(30.0)
    y = 2 * x + 4
    x[5] = np.nan
    y[10] = np.nan
    before = x.copy(), y.copy()
    result = scatter.compute_statistics_robust(x, y, correct_autocorrelation=False)
    assert result["n"] == 28 and result["r"] == pytest.approx(1)
    assert result["slope"] == pytest.approx(2) and result["intercept"] == pytest.approx(4)
    np.testing.assert_equal(x, before[0])
    np.testing.assert_equal(y, before[1])


@pytest.mark.parametrize("paired", [False, True])
def test_cohens_effect_size_matches_independent_sample_variance(paired):
    control = np.array([1.0, 2, 4, 8])
    treatment = np.array([3.0, 3, 7, 12])
    if paired:
        differences = treatment - control
        expected = differences.mean() / differences.std(ddof=1)
    else:
        expected = (treatment.mean() - control.mean()) / np.sqrt((control.var(ddof=1) + treatment.var(ddof=1)) / 2)
    assert scatter.compute_cohens_d(control, treatment, paired) == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("method,oracle", [("wilcoxon", wilcoxon), ("ttest", ttest_rel)])
def test_paired_tests_use_the_same_subject_order(method, oracle):
    control = np.array([1.0, 2, 4, 8, 11])
    treatment = np.array([2.0, 4, 3, 10, 12])
    actual = scatter.paired_statistical_test(control, treatment, method)
    expected = oracle(control, treatment)
    assert actual[:2] == pytest.approx((expected.statistic, expected.pvalue))
    insufficient = scatter.paired_statistical_test(control[:3], treatment[:3], method)
    assert np.isnan(insufficient[:2]).all() and insufficient[2] == "insufficient_n"


def test_population_drops_invalid_subject_pairs_together_and_records_subjects():
    collector = scatter.PopulationCorrelationCollector("drug")
    assert not collector.has_data()
    assert collector.compute_population_statistics()["error"] == "Insufficient valid subjects"
    control = [0.1, 0.2, np.nan, 0.4, 0.5]
    treatment = [0.2, 0.4, 0.5, 0.3, 0.8]
    for subject, c, tr in zip(range(1, 6), control, treatment):
        collector.add_subject(subject, {"r": c}, {"r": tr})
    np.random.seed(71)
    result = collector.compute_population_statistics(bootstrap_iterations=200)
    assert result["subjects"] == [1, 2, 3, 4, 5]
    assert result["n_subjects"] == 5 and result["n_valid"] == 4
    assert result["control"]["values"] == [0.1, 0.2, 0.4, 0.5]
    assert result["treatment"]["values"] == [0.2, 0.4, 0.3, 0.8]
    assert result["comparison"]["p_value"] == pytest.approx(wilcoxon([0.1, 0.2, 0.4, 0.5], [0.2, 0.4, 0.3, 0.8]).pvalue)
    assert result["control"]["sem"] == pytest.approx(np.std([0.1, 0.2, 0.4, 0.5], ddof=1) / 2)
    for key in ("control", "treatment"):
        assert result[key]["min"] <= result[key]["ci_lower"] <= result[key]["ci_upper"] <= result[key]["max"]


@pytest.mark.parametrize("gaps", [False, True])
def test_real_subject_pipeline_tracks_known_correlation_and_excludes_long_gaps(tmp_path, gaps):
    fr = 20
    base = np.sin(2 * np.pi * 2 * np.arange(800) / fr)
    eeg = np.r_[base, base]
    calcium = eeg * 3
    if gaps:
        eeg[100:140] = np.nan
        calcium[120:160] = np.nan
    before = eeg.copy(), calcium.copy()
    config = StatsConfig(
        lowcut=1, highcut=4, headless=True, plot_formats=[], edge_trim_seconds=1, correct_autocorrelation=False
    )
    collector = scatter.PopulationCorrelationCollector("drug")
    success, control, treatment = scatter.ScatterAnalysis(config).run_subject(
        eeg, calcium, fr, 7, "drug", {7: [[0, 40 / 60], [40 / 60, 80 / 60]]}, "EEG", tmp_path, collector
    )
    assert success
    assert treatment["r"] == pytest.approx(1) and treatment["n"] == 760
    assert control["n"] == (700 if gaps else 760)
    if not gaps:
        assert control["r"] == pytest.approx(1)
    assert collector.subjects == [7]
    np.testing.assert_equal(eeg, before[0])
    np.testing.assert_equal(calcium, before[1])


def test_missing_subject_windows_return_failure_and_do_not_add_population_subject(tmp_path):
    collector = scatter.PopulationCorrelationCollector("drug")
    result = scatter.ScatterAnalysis(StatsConfig(headless=True)).run_subject(
        np.ones(100), np.ones(100), 20, 7, "drug", {}, "EEG", tmp_path, collector
    )
    assert result == (False, None, None) and not collector.has_data()
