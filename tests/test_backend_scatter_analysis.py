"""Known-answer correlations, uncertainty, paired subjects, and gap masks."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pytest
from scipy.stats import norm, t, ttest_rel, wilcoxon

from aceneurotools.multimodal import scatter_analysis as scatter
from aceneurotools.multimodal import signal_utils
from aceneurotools.multimodal.stats_config import StatsConfig


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


@pytest.mark.parametrize(
    "gap_case",
    [
        [],
        [(100, 140, 20)],
        [(100, 140, 20), (500, 540, 20)],
        [(0, 12, 0)],
    ],
    ids=["gap_free", "single_gap", "two_disjoint_gaps", "gap_inside_trimmed_edge"],
)
def test_real_subject_pipeline_tracks_known_correlation_and_excludes_long_gaps(tmp_path, gap_case):
    """The gap margin must be applied exactly, with a visible nonlinear relation.

    ``calcium = 3*eeg + 1.5*eeg**2`` is deliberately nonlinear. With the old
    ``calcium = 3*eeg`` construction the pipeline returned r == 1 for every
    mask, so contaminated gap-adjacent samples were invisible. Here the
    excluded count and the z-scored statistics must match an independent
    oracle mask built by explicit index arithmetic.
    """
    fr = 20
    base = np.sin(2 * np.pi * 2 * np.arange(800) / fr)
    eeg = np.r_[base, base]
    calcium = 3 * eeg + 1.5 * eeg**2
    for start, stop, offset in gap_case:
        eeg[start:stop] = np.nan
        calcium[start + offset : stop + offset] = np.nan
    before = eeg.copy(), calcium.copy()
    config = StatsConfig(
        lowcut=1, highcut=4, headless=True, plot_formats=[], edge_trim_seconds=1, correct_autocorrelation=False
    )
    selections = {7: [[0, 40 / 60], [40 / 60, 80 / 60]]}
    collector = scatter.PopulationCorrelationCollector("drug")
    success, control, treatment = scatter.ScatterAnalysis(config).run_subject(
        eeg, calcium, fr, 7, "drug", selections, "EEG", tmp_path, collector
    )
    assert success
    assert collector.subjects == [7]
    np.testing.assert_equal(eeg, before[0])
    np.testing.assert_equal(calcium, before[1])

    # Sampling arithmetic: 800-sample window, trimmed by edge_trim_seconds on
    # both sides; each merged gap run (EEG ∪ calcium) plus one margin per side
    # is excluded. Runs are interior, so nothing is boundary-clipped.
    trim = int(config.edge_trim_seconds * fr)
    margin = trim  # the transient margin reuses the edge-trim width
    trimmed_total = 800 - 2 * trim
    gap_runs = _union_gap_runs(gap_case)
    excluded = sum(max(0, min(800 - trim, hi + margin) - max(trim, lo - margin)) for lo, hi in gap_runs)
    assert control["n"] == trimmed_total - excluded
    assert treatment["n"] == trimmed_total  # treatment window has no gaps

    expected, oracle_mask = _oracle_control_stats(eeg, calcium, config, fr, selections, 7, margin)
    assert control["n"] == expected["n"] == int(oracle_mask.sum())
    for key in ("r", "slope", "intercept", "n_effective"):
        assert control[key] == pytest.approx(expected[key], rel=1e-12, abs=1e-15)
    # The relation is genuinely nonlinear, so a mask defect cannot hide
    # behind r == 1 as it did with calcium = eeg * 3.
    assert control["r"] < 0.999


def _union_gap_runs(gap_case):
    """Merge EEG and calcium gaps into maximal excluded runs (indices in samples)."""
    runs = []
    for start, stop, offset in gap_case:
        runs.extend([(start, stop), (start + offset, stop + offset)])
    runs.sort()
    merged: list[tuple[int, int]] = []
    for lo, hi in runs:
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged


def _oracle_control_stats(eeg, calcium, config, fr, selections, line_num, margin):
    """Independent expected control-window statistics.

    Rebuilds the filtered arrays with the documented utilities and derives the
    excluded mask by explicit index arithmetic on the runs of the actual
    validity mask — the margin is computed from run starts/ends in a plain
    loop and ``mask_filter_transients`` is never called. Returns
    ``(stats, mask)``.
    """
    eeg_clean, eeg_valid = signal_utils.handle_nans(eeg, fr, max_gap_seconds=0.5)
    ca_clean, ca_valid = signal_utils.handle_nans(calcium, fr, max_gap_seconds=0.5)
    ctrl_eeg, treat_eeg = signal_utils.slice_signal(eeg_clean, selections, line_num, fr)
    ctrl_ca, treat_ca = signal_utils.slice_signal(ca_clean, selections, line_num, fr)
    ctrl_valid, _ = signal_utils.slice_signal(eeg_valid & ca_valid, selections, line_num, fr)

    fe_ctrl, fc_ctrl = signal_utils.filter_signals(
        ctrl_eeg, ctrl_ca, fr, [config.lowcut, config.highcut], config.filter_order
    )
    fe_treat, fc_treat = signal_utils.filter_signals(
        treat_eeg, treat_ca, fr, [config.lowcut, config.highcut], config.filter_order
    )
    fe_ctrl = signal_utils.trim_filter_edges(fe_ctrl, fr, config.edge_trim_seconds)
    fc_ctrl = signal_utils.trim_filter_edges(fc_ctrl, fr, config.edge_trim_seconds)
    fe_treat = signal_utils.trim_filter_edges(fe_treat, fr, config.edge_trim_seconds)
    fc_treat = signal_utils.trim_filter_edges(fc_treat, fr, config.edge_trim_seconds)
    mask = ctrl_valid.copy()
    excluded_idx = np.flatnonzero(~ctrl_valid)
    if excluded_idx.size:
        boundaries = np.flatnonzero(np.diff(excluded_idx) > 1)
        starts = excluded_idx[np.r_[0, boundaries + 1]]
        ends = excluded_idx[np.r_[boundaries, excluded_idx.size - 1]]
        for start, end in zip(starts, ends):
            mask[max(0, start - margin) : min(mask.size, end + margin + 1)] = False

    mask = signal_utils.trim_filter_edges(mask, fr, config.edge_trim_seconds)
    fe_ctrl[~mask] = np.nan
    fc_ctrl[~mask] = np.nan
    ne_ctrl, _, nc_ctrl, _, _ = signal_utils.normalize_signals_global(fe_ctrl, fe_treat, fc_ctrl, fc_treat)
    stats = scatter.compute_statistics_robust(nc_ctrl, ne_ctrl, fr, config.correct_autocorrelation)
    return stats, mask


def test_segment_fully_masked_by_gap_margin_returns_nan_stats_without_crashing(tmp_path):
    """A control window consumed by a gap plus its transient margins must not crash."""
    fr = 20
    time = np.arange(180) / fr
    eeg = np.sin(2 * np.pi * 2 * time)
    calcium = 3 * eeg + 1.5 * eeg**2
    # 2 s gap covers the control interior: after the 1 s edge trim and the 1 s
    # margin on each side, no control sample remains valid.
    eeg[30:70] = np.nan
    calcium[30:70] = np.nan
    config = StatsConfig(
        lowcut=1, highcut=4, headless=True, plot_formats=[], edge_trim_seconds=1, correct_autocorrelation=False
    )
    selections = {7: [[0, 90 / fr / 60], [90 / fr / 60, 180 / fr / 60]]}
    collector = scatter.PopulationCorrelationCollector("drug")
    success, control, treatment = scatter.ScatterAnalysis(config).run_subject(
        eeg, calcium, fr, 7, "drug", selections, "EEG", tmp_path, collector
    )
    assert success  # statistics and plotting tolerate the all-NaN control segment
    assert control["n"] == 0
    assert np.isnan([control["r"], control["slope"], control["intercept"]]).all()
    assert treatment["n"] == 50 and np.isfinite(treatment["r"])
    assert collector.subjects == [7]


def test_missing_subject_windows_return_failure_and_do_not_add_population_subject(tmp_path):
    collector = scatter.PopulationCorrelationCollector("drug")
    result = scatter.ScatterAnalysis(StatsConfig(headless=True)).run_subject(
        np.ones(100), np.ones(100), 20, 7, "drug", {}, "EEG", tmp_path, collector
    )
    assert result == (False, None, None) and not collector.has_data()
