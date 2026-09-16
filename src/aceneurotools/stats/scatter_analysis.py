"""
EEG–Calcium scatter and population correlation analysis for ACE-NeuroTools.

This module ports the statistical and visualisation logic for the ACE-NeuroTools package.

Key components
--------------
* Statistical functions — Pearson r with autocorrelation-corrected effective N
  and Fisher-z confidence intervals; bootstrap CIs; Cohen's d; paired tests.
* :class:`PopulationCorrelationCollector` — accumulates per-subject results for
  a single drug condition.
* Plotting functions — individual scatter and hexbin, combined overlays,
  population violin plots, cross-drug summary bars.
* :class:`ScatterAnalysis` — high-level orchestrator that processes one subject
  and optionally accumulates into a population collector.

Typical use::

    from aceneurotools.stats.scatter_analysis import ScatterAnalysis, PopulationCorrelationCollector
    from aceneurotools.config.stats_config import StatsConfig, StudyMetadata

    config   = StatsConfig()
    metadata = StudyMetadata.default()

    # Per-drug collector
    collector = PopulationCorrelationCollector("dexmedetomidine: 0.00045")

    engine = ScatterAnalysis(config)
    for line_num in metadata.drug_groups["dexmedetomidine: 0.00045"]:
        # (load signals first via stats.loader)
        engine.run_subject(
            eeg_signal=eeg, calcium_signal=ca,
            fr=fr, line_num=line_num,
            drug=metadata.drug_of(line_num),
            selections=metadata.selections,
            channel="CBvsPCEEG",
            output_dir="/results/scatter",
            collector=collector,
        )

    pop_stats = collector.compute_population_statistics()
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import scipy
from scipy import stats as scipy_stats
from scipy.stats import pearsonr
from scipy.stats import t as t_dist

from aceneurotools.config.stats_config import StatsConfig
from aceneurotools.stats.signal_utils import (
    handle_nans,
    normalize_signals_global,
    slice_signal,
    trim_filter_edges,
)

# Optional: statsmodels for ACF-based effective-N estimation
try:
    from statsmodels.tsa.stattools import acf as _statsmodels_acf
    _HAS_STATSMODELS = True
except ImportError:
    _HAS_STATSMODELS = False

# Figure style constants

_SINGLE_COL = 3.35   # inches — 8.5 cm (eNeuro single column)
_DOUBLE_COL = 7.0    # inches — 17.8 cm

_COLORS = {
    "control":          "#969696",
    "treatment":        "#252525",
    "edge":             "#000000",
    "regression":       "#000000",
    "regression_ctrl":  "#666666",
    "regression_treat": "#000000",
}
_POP_COLORS = {
    "violin_control":   "#A8D5BA",
    "violin_treatment": "#F4A6A6",
    "violin_alpha":     0.7,
    "point":            "#2C3E50",
    "point_size":       30,
    "line":             "#7F8C8D",
    "line_alpha":       0.5,
}
_MARKERS = {"control": "o", "treatment": "s"}
_FONTS   = {"axis": 9, "tick": 8, "annotation": 7, "title": 10, "stats": 7}

_CHANNEL_DESCRIPTIONS = {
    "CBvsPCEEG":       "Cerebellum vs Parietal Cortex EEG",
    "PFCLFPvsCBEEG":   "Prefrontal Cortex LFP vs Cerebellum EEG",
    "PFCEEGvsCBEEG":   "Prefrontal Cortex EEG vs Cerebellum EEG",
}


# Statistical functions

def estimate_effective_sample_size(
    x: np.ndarray,
    y: np.ndarray,
    max_lags: int = 100,
) -> float:
    """Estimate effective sample size accounting for serial autocorrelation.

    Uses the Pyke & Fernholz formula: N_eff = N / (1 + 2 Σ ρ_x(k) ρ_y(k)).
    Falls back to raw N when statsmodels is unavailable.

    Args:
        x: First signal.
        y: Second signal (same length as *x*).
        max_lags: Maximum ACF lag to compute.

    Returns:
        Effective sample size clamped to [3, N].
    """
    n = len(x)
    if not _HAS_STATSMODELS:
        return float(n)

    max_lags = min(max_lags, n // 4)
    try:
        acf_x = _statsmodels_acf(x, nlags=max_lags, fft=True)
        acf_y = _statsmodels_acf(y, nlags=max_lags, fft=True)
        rho_sum = float(np.sum(acf_x[1:] * acf_y[1:]))
        n_eff   = n / (1.0 + 2.0 * max(0.0, rho_sum))
        return float(max(3.0, min(n_eff, n)))
    except Exception:
        return float(n)


def compute_confidence_interval(
    r: float,
    n_effective: float,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Fisher z-transform confidence interval for a Pearson correlation.

    Args:
        r: Pearson correlation coefficient.
        n_effective: Effective sample size.
        confidence: Desired confidence level (0–1).

    Returns:
        ``(ci_lower, ci_upper)`` on the correlation scale, or ``(nan, nan)``
        when *n_effective* ≤ 3 or *r* is undefined.
    """
    if n_effective <= 3 or np.isnan(r) or abs(r) >= 1.0:
        return float("nan"), float("nan")
    z    = np.arctanh(r)
    se   = 1.0 / np.sqrt(n_effective - 3.0)
    z_c  = scipy.stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0)
    return float(np.tanh(z - z_c * se)), float(np.tanh(z + z_c * se))


def compute_statistics_robust(
    x: np.ndarray,
    y: np.ndarray,
    fr: float = 30.0,
    correct_autocorrelation: bool = True,
    confidence_level: float = 0.95,
    max_acf_lags: int = 100,
) -> dict:
    """Pearson correlation with autocorrelation-corrected effective N.

    Args:
        x: First signal (e.g., calcium).
        y: Second signal (e.g., EEG).
        fr: Sampling rate (used only for documentation; no resampling).
        correct_autocorrelation: Apply effective-N correction.
        confidence_level: Confidence interval level.
        max_acf_lags: Passed to :func:`estimate_effective_sample_size`.

    Returns:
        Dict with keys: ``n``, ``n_effective``, ``r``, ``p_value``,
        ``p_value_corrected``, ``ci_lower``, ``ci_upper``, ``slope``,
        ``intercept``, ``p_value_str``, ``p_value_corrected_str``.
    """
    valid = ~(np.isnan(x) | np.isnan(y))
    xv, yv = x[valid], y[valid]

    result: dict = {
        "n": len(xv), "n_effective": float("nan"),
        "r": float("nan"), "p_value": float("nan"),
        "p_value_corrected": float("nan"),
        "ci_lower": float("nan"), "ci_upper": float("nan"),
        "slope": float("nan"), "intercept": float("nan"),
        "p_value_str": "N/A", "p_value_corrected_str": "N/A",
    }

    if len(xv) < 10:
        return result

    r, p_value = pearsonr(xv, yv)
    coeffs     = np.polyfit(xv, yv, 1)
    result.update({"r": float(r), "p_value": float(p_value),
                   "slope": float(coeffs[0]), "intercept": float(coeffs[1])})
    result["p_value_str"] = _fmt_p(p_value)

    if correct_autocorrelation:
        n_eff = estimate_effective_sample_size(xv, yv, max_acf_lags)
        result["n_effective"] = int(n_eff)
        if n_eff > 2:
            t_stat = r * np.sqrt((n_eff - 2.0) / (1.0 - r ** 2 + 1e-10))
            p_corr = float(2.0 * t_dist.sf(abs(t_stat), n_eff - 2.0))
            result["p_value_corrected"] = p_corr
            result["p_value_corrected_str"] = _fmt_p(p_corr)
        ci_lo, ci_hi = compute_confidence_interval(r, n_eff, confidence_level)
        result["ci_lower"], result["ci_upper"] = ci_lo, ci_hi
    else:
        result["n_effective"]          = int(len(xv))
        result["p_value_corrected"]    = float(p_value)
        result["p_value_corrected_str"]= result["p_value_str"]

    return result


def compute_cohens_d(group1: np.ndarray, group2: np.ndarray, paired: bool = True) -> float:
    """Cohen's d effect size (paired or independent groups).

    Args:
        group1: Control group.
        group2: Treatment group.
        paired: If True, compute from paired differences.

    Returns:
        Cohen's d.
    """
    if paired:
        diff = group2 - group1
        return float(np.mean(diff) / (np.std(diff, ddof=1) + 1e-10))
    n1, n2 = len(group1), len(group2)
    v1, v2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled = np.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    return float((np.mean(group2) - np.mean(group1)) / (pooled + 1e-10))


def _interpret_cohens_d(d: float) -> str:
    d_abs = abs(d)
    if d_abs < 0.2:  return "negligible"
    if d_abs < 0.5:  return "small"
    if d_abs < 0.8:  return "medium"
    return "large"


def bootstrap_ci(
    data: np.ndarray,
    statistic: str = "median",
    n_bootstrap: int = 10_000,
    confidence: float = 0.95,
) -> tuple[float, float, float]:
    """Bootstrap confidence interval for a statistic.

    Args:
        data: 1-D array of values.
        statistic: ``'median'`` or ``'mean'``.
        n_bootstrap: Number of resamples.
        confidence: Confidence level (0–1).

    Returns:
        ``(point_estimate, ci_lower, ci_upper)``
    """
    fn    = np.median if statistic == "median" else np.mean
    point = fn(data)
    bs    = np.array([fn(np.random.choice(data, size=len(data), replace=True)) for _ in range(n_bootstrap)])
    alpha = 1.0 - confidence
    return float(point), float(np.percentile(bs, 100 * alpha / 2)), float(np.percentile(bs, 100 * (1 - alpha / 2)))


def paired_statistical_test(
    control: np.ndarray,
    treatment: np.ndarray,
    test_type: str = "wilcoxon",
    min_n: int = 4,
) -> tuple[float, float, str]:
    """Paired statistical comparison of control vs treatment.

    Args:
        control:   Control group (one value per subject).
        treatment: Treatment group (same subjects, same order).
        test_type: ``'wilcoxon'`` (default) or ``'ttest'``.
        min_n:     Minimum group size; returns NaN when not met.

    Returns:
        ``(test_statistic, p_value, test_name)``
    """
    if len(control) < min_n:
        return float("nan"), float("nan"), "insufficient_n"
    if test_type == "wilcoxon":
        try:
            stat, p = scipy_stats.wilcoxon(control, treatment, alternative="two-sided")
            return float(stat), float(p), "Wilcoxon signed-rank"
        except ValueError:
            stat, p = scipy_stats.ttest_rel(control, treatment)
            return float(stat), float(p), "Paired t-test (fallback)"
    stat, p = scipy_stats.ttest_rel(control, treatment)
    return float(stat), float(p), "Paired t-test"


def _fmt_p(p: float) -> str:
    if np.isnan(p):       return "N/A"
    if p < 0.001:         return "p < 0.001"
    if p < 0.05:          return f"p = {p:.3f}"
    return f"p = {p:.3f}"


def _fmt_p_stars(p: float) -> str:
    if np.isnan(p): return ""
    if p < 0.001:   return "***"
    if p < 0.01:    return "**"
    if p < 0.05:    return "*"
    return "n.s."


def _fmt_drug_short(drug: str) -> str:
    if "dexmedetomidine" in drug.lower():
        dose = drug.split(": ")[1] if ": " in drug else ""
        return f"Dex {dose}" if dose else "Dex"
    if drug.lower() == "sleep":
        return "Sleep"
    return drug.capitalize()


# Population accumulator

class PopulationCorrelationCollector:
    """Accumulate per-subject correlation statistics for population analysis.

    Args:
        drug_name: Label for the drug condition this collector covers.
    """

    def __init__(self, drug_name: str) -> None:
        self.drug_name              = drug_name
        self.subjects:              list[int]   = []
        self.control_correlations:  list[float] = []
        self.treatment_correlations:list[float] = []
        self.control_ci_lower:      list[float] = []
        self.control_ci_upper:      list[float] = []
        self.treatment_ci_lower:    list[float] = []
        self.treatment_ci_upper:    list[float] = []
        self.control_n_effective:   list[float] = []
        self.treatment_n_effective: list[float] = []

    def add_subject(self, line_num: int, control_stats: dict, treatment_stats: dict) -> None:
        """Append statistics for one subject."""
        self.subjects.append(line_num)
        self.control_correlations.append(  float(control_stats.get("r",           float("nan"))))
        self.treatment_correlations.append(float(treatment_stats.get("r",          float("nan"))))
        self.control_ci_lower.append(      float(control_stats.get("ci_lower",     float("nan"))))
        self.control_ci_upper.append(      float(control_stats.get("ci_upper",     float("nan"))))
        self.treatment_ci_lower.append(    float(treatment_stats.get("ci_lower",   float("nan"))))
        self.treatment_ci_upper.append(    float(treatment_stats.get("ci_upper",   float("nan"))))
        self.control_n_effective.append(   float(control_stats.get("n_effective",  float("nan"))))
        self.treatment_n_effective.append( float(treatment_stats.get("n_effective",float("nan"))))

    def has_data(self) -> bool:
        """Return True if at least one subject has been added."""
        return len(self.subjects) > 0

    def get_arrays(self) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(control_r, treatment_r)`` as NumPy arrays."""
        return np.array(self.control_correlations), np.array(self.treatment_correlations)

    def compute_population_statistics(
        self,
        bootstrap_iterations: int = 10_000,
        confidence_level: float = 0.95,
        paired_test: str = "wilcoxon",
        min_n: int = 4,
    ) -> dict:
        """Compute comprehensive population-level statistics.

        Returns:
            Dict with keys: ``drug_name``, ``n_subjects``, ``n_valid``,
            ``subjects``, ``control``, ``treatment``, ``comparison``.
        """
        ctrl  = np.array(self.control_correlations)
        treat = np.array(self.treatment_correlations)
        valid = ~(np.isnan(ctrl) | np.isnan(treat))
        cv, tv = ctrl[valid], treat[valid]
        n_valid = int(np.sum(valid))

        out: dict = {
            "drug_name":  self.drug_name,
            "n_subjects": len(self.subjects),
            "n_valid":    n_valid,
            "subjects":   self.subjects,
        }
        if n_valid < 2:
            out["error"] = "Insufficient valid subjects"
            return out

        c_med, c_lo, c_hi = bootstrap_ci(cv, "median", bootstrap_iterations, confidence_level)
        t_med, t_lo, t_hi = bootstrap_ci(tv, "median", bootstrap_iterations, confidence_level)

        out["control"] = {
            "median": c_med, "mean": float(np.mean(cv)),
            "std":    float(np.std(cv, ddof=1)),
            "sem":    float(np.std(cv, ddof=1) / np.sqrt(n_valid)),
            "ci_lower": c_lo, "ci_upper": c_hi,
            "min": float(np.min(cv)), "max": float(np.max(cv)),
            "values": cv.tolist(),
        }
        out["treatment"] = {
            "median": t_med, "mean": float(np.mean(tv)),
            "std":    float(np.std(tv, ddof=1)),
            "sem":    float(np.std(tv, ddof=1) / np.sqrt(n_valid)),
            "ci_lower": t_lo, "ci_upper": t_hi,
            "min": float(np.min(tv)), "max": float(np.max(tv)),
            "values": tv.tolist(),
        }

        stat, p, test_name = paired_statistical_test(cv, tv, paired_test, min_n)
        d = compute_cohens_d(cv, tv, paired=True)
        out["comparison"] = {
            "test_name":                 test_name,
            "test_statistic":            float(stat) if not np.isnan(stat) else None,
            "p_value":                   float(p),
            "p_value_str":               _fmt_p_stars(p),
            "cohens_d":                  float(d),
            "effect_size_interpretation":_interpret_cohens_d(d),
            "mean_difference":           float(np.mean(tv - cv)),
            "median_difference":         float(np.median(tv - cv)),
        }
        return out

# Individual-subject plotting

def _save_fig(fig: plt.Figure, base: Path, formats: list[str], dpi: int) -> None:
    base.parent.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        p = Path(str(base) + f".{fmt}")
        kw: dict = {"dpi": dpi, "bbox_inches": "tight"}
        if fmt in ("tiff", "tif"):
            kw["pil_kwargs"] = {"compression": "tiff_lzw"}
        try:
            fig.savefig(str(p), **kw)
        except Exception as exc:
            warnings.warn(f"Could not save {p}: {exc}", stacklevel=2)


def create_scatter_plot(
    calcium_signal: np.ndarray,
    eeg_signal: np.ndarray,
    line_num: int,
    drug: str,
    period: str,
    channel: str,
    fr: float,
    time_window: list[float],
    config: StatsConfig,
    save_path: Path | None = None,
) -> tuple[plt.Figure, dict]:
    """Single-condition scatter plot of calcium vs EEG with regression line."""
    fig, ax = plt.subplots(figsize=(_SINGLE_COL, _SINGLE_COL))
    color  = _COLORS["control"]  if period == "Control"   else _COLORS["treatment"]
    marker = _MARKERS["control"] if period == "Control"   else _MARKERS["treatment"]

    ax.scatter(calcium_signal, eeg_signal, c=color, marker=marker,
               s=1, alpha=0.3, edgecolors="none", rasterized=True)

    st = compute_statistics_robust(calcium_signal, eeg_signal, fr,
                                   config.correct_autocorrelation,
                                   config.confidence_level, config.max_acf_lags)
    if st["n"] > 2 and not np.isnan(st["r"]):
        valid = ~(np.isnan(calcium_signal) | np.isnan(eeg_signal))
        xv    = calcium_signal[valid]
        p_fn  = np.poly1d([st["slope"], st["intercept"]])
        xl    = np.linspace(xv.min(), xv.max(), 100)
        ax.plot(xl, p_fn(xl), color=_COLORS["regression"], linestyle="--", linewidth=1)

        ci_str = (f"\n95% CI [{st['ci_lower']:.2f}, {st['ci_upper']:.2f}]"
                  if not np.isnan(st["ci_lower"]) else "")
        txt = (f"n={st['n']:,}\nn_eff={st['n_effective']:,}\n"
               f"r={st['r']:.3f}{ci_str}\n{st['p_value_corrected_str']}")
        ax.text(0.02, 0.98, txt, transform=ax.transAxes, fontsize=_FONTS["annotation"],
                va="top", bbox=dict(boxstyle="round", fc="white", ec="black", lw=0.5, alpha=0.9))

    ax.set_xlabel("Calcium (z-score)", fontsize=_FONTS["axis"])
    ax.set_ylabel("EEG (z-score)",     fontsize=_FONTS["axis"])
    ax.tick_params(labelsize=_FONTS["tick"])
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, alpha=0.3, linewidth=0.5, linestyle=":")
    plt.tight_layout()

    if save_path:
        _save_fig(fig, save_path, config.plot_formats, config.color_dpi)
    if not config.headless:
        plt.show()
    plt.close(fig)
    return fig, st


def create_hexbin_plot(
    calcium_signal: np.ndarray,
    eeg_signal: np.ndarray,
    line_num: int,
    drug: str,
    period: str,
    channel: str,
    fr: float,
    time_window: list[float],
    config: StatsConfig,
    save_path: Path | None = None,
) -> tuple[plt.Figure, dict]:
    """Hexbin density plot with regression line overlay."""
    fig, ax = plt.subplots(figsize=(_SINGLE_COL, _SINGLE_COL))
    st = compute_statistics_robust(calcium_signal, eeg_signal, fr,
                                   config.correct_autocorrelation,
                                   config.confidence_level, config.max_acf_lags)
    valid = ~(np.isnan(calcium_signal) | np.isnan(eeg_signal))
    xv, yv = calcium_signal[valid], eeg_signal[valid]

    if len(xv) < 10:
        plt.close(fig)
        return fig, st

    hb = ax.hexbin(xv, yv, gridsize=50, cmap="plasma", mincnt=1, edgecolors="none")
    cb = fig.colorbar(hb, ax=ax)
    cb.set_label("Count", fontsize=_FONTS["axis"])
    cb.ax.tick_params(labelsize=_FONTS["tick"])

    if st["n"] > 2 and not np.isnan(st["r"]):
        p_fn = np.poly1d([st["slope"], st["intercept"]])
        xl   = np.linspace(xv.min(), xv.max(), 100)
        ax.plot(xl, p_fn(xl), color="red", linestyle="--", linewidth=1.5)
        ci_str = (f"\n95% CI [{st['ci_lower']:.2f}, {st['ci_upper']:.2f}]"
                  if not np.isnan(st["ci_lower"]) else "")
        txt = f"n={st['n']:,}\nn_eff={st['n_effective']:,}\nr={st['r']:.3f}{ci_str}\n{st['p_value_corrected_str']}"
        ax.text(0.02, 0.98, txt, transform=ax.transAxes, fontsize=_FONTS["annotation"],
                va="top", bbox=dict(boxstyle="round", fc="white", ec="black", lw=0.5, alpha=0.9))

    ax.set_xlabel("Calcium (z-score)", fontsize=_FONTS["axis"])
    ax.set_ylabel("EEG (z-score)",     fontsize=_FONTS["axis"])
    ax.tick_params(labelsize=_FONTS["tick"])
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()

    if save_path:
        _save_fig(fig, save_path, config.plot_formats, config.color_dpi)
    if not config.headless:
        plt.show()
    plt.close(fig)
    return fig, st


def create_combined_scatter_plot(
    calcium_ctrl: np.ndarray, eeg_ctrl: np.ndarray,
    calcium_treat: np.ndarray, eeg_treat: np.ndarray,
    line_num: int, drug: str, channel: str, fr: float,
    time_window_ctrl: list[float], time_window_treat: list[float],
    config: StatsConfig,
    save_path: Path | None = None,
) -> tuple[plt.Figure, dict, dict]:
    """Overlay scatter of control (gray) and treatment (black) with separate regression lines."""
    fig, ax = plt.subplots(figsize=(_SINGLE_COL, _SINGLE_COL))
    ax.scatter(calcium_ctrl,  eeg_ctrl,  c=_COLORS["control"],   marker=_MARKERS["control"],
               s=1, alpha=0.2, edgecolors="none", rasterized=True, label="Control")
    ax.scatter(calcium_treat, eeg_treat, c=_COLORS["treatment"], marker=_MARKERS["treatment"],
               s=1, alpha=0.2, edgecolors="none", rasterized=True, label="Treatment")

    sc = compute_statistics_robust(calcium_ctrl,  eeg_ctrl,  fr,
                                   config.correct_autocorrelation, config.confidence_level, config.max_acf_lags)
    st = compute_statistics_robust(calcium_treat, eeg_treat, fr,
                                   config.correct_autocorrelation, config.confidence_level, config.max_acf_lags)

    label_txt = ""
    for stats_d, color, style, lbl in [
        (sc, _COLORS["regression_ctrl"],  "--", f"Ctrl: r={sc.get('r', float('nan')):.3f}"),
        (st, _COLORS["regression_treat"], "-",  f"Treat: r={st.get('r', float('nan')):.3f}"),
    ]:
        if stats_d["n"] > 2 and not np.isnan(stats_d["r"]):
            valid = ~(np.isnan(calcium_ctrl if color == _COLORS["regression_ctrl"] else calcium_treat)
                      | np.isnan(eeg_ctrl   if color == _COLORS["regression_ctrl"] else eeg_treat))
            xv = (calcium_ctrl if color == _COLORS["regression_ctrl"] else calcium_treat)[valid]
            xl = np.linspace(xv.min(), xv.max(), 100)
            ax.plot(xl, np.poly1d([stats_d["slope"], stats_d["intercept"]])(xl),
                    color=color, linestyle=style, linewidth=1.5)
            label_txt += lbl + "\n"

    if label_txt:
        ax.text(0.02, 0.98, label_txt.strip(), transform=ax.transAxes,
                fontsize=_FONTS["annotation"], va="top",
                bbox=dict(boxstyle="round", fc="white", ec="black", lw=0.5, alpha=0.9))

    ax.legend(loc="lower right", fontsize=_FONTS["annotation"], frameon=True, markerscale=5)
    ax.set_xlabel("Calcium (z-score)", fontsize=_FONTS["axis"])
    ax.set_ylabel("EEG (z-score)",     fontsize=_FONTS["axis"])
    ax.tick_params(labelsize=_FONTS["tick"])
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, alpha=0.3, linewidth=0.5, linestyle=":")
    plt.tight_layout()

    if save_path:
        _save_fig(fig, save_path, config.plot_formats, config.color_dpi)
    if not config.headless:
        plt.show()
    plt.close(fig)
    return fig, sc, st


def create_combined_hexbin_plot(
    calcium_ctrl: np.ndarray, eeg_ctrl: np.ndarray,
    calcium_treat: np.ndarray, eeg_treat: np.ndarray,
    line_num: int, drug: str, channel: str, fr: float,
    time_window_ctrl: list[float], time_window_treat: list[float],
    config: StatsConfig,
    save_path: Path | None = None,
) -> tuple[plt.Figure, dict, dict]:
    """Side-by-side hexbin panels for control and treatment."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(_DOUBLE_COL, _SINGLE_COL))

    sc = compute_statistics_robust(calcium_ctrl,  eeg_ctrl,  fr,
                                   config.correct_autocorrelation, config.confidence_level, config.max_acf_lags)
    st = compute_statistics_robust(calcium_treat, eeg_treat, fr,
                                   config.correct_autocorrelation, config.confidence_level, config.max_acf_lags)

    all_x = np.concatenate([calcium_ctrl[~np.isnan(calcium_ctrl)], calcium_treat[~np.isnan(calcium_treat)]])
    all_y = np.concatenate([eeg_ctrl[~np.isnan(eeg_ctrl)],         eeg_treat[~np.isnan(eeg_treat)]])
    if len(all_x) == 0 or len(all_y) == 0:
        warnings.warn(f"No valid data for combined hexbin (line {line_num}) — skipping.", stacklevel=2)
        plt.close(fig)
        return fig, {}, {}
    xlo, xhi = np.percentile(all_x, [1, 99])
    ylo, yhi = np.percentile(all_y, [1, 99])

    for ax, ca, ee, stats_d, title in [
        (ax1, calcium_ctrl,  eeg_ctrl,  sc, "Control"),
        (ax2, calcium_treat, eeg_treat, st, "Treatment"),
    ]:
        valid = ~(np.isnan(ca) | np.isnan(ee))
        if valid.sum() >= 10:
            hb = ax.hexbin(ca[valid], ee[valid], gridsize=40, cmap="plasma",
                           mincnt=1, edgecolors="none", extent=[xlo, xhi, ylo, yhi])
            if ax is ax2:
                cb = fig.colorbar(hb, ax=ax)
                cb.set_label("Count", fontsize=_FONTS["axis"])
                cb.ax.tick_params(labelsize=_FONTS["tick"])
            if stats_d["n"] > 2 and not np.isnan(stats_d["r"]):
                xl = np.linspace(xlo, xhi, 100)
                ax.plot(xl, np.poly1d([stats_d["slope"], stats_d["intercept"]])(xl),
                        "r--", linewidth=1.5)
                ax.text(0.02, 0.98,
                        f"r={stats_d['r']:.3f}\nn_eff={stats_d['n_effective']:,}",
                        transform=ax.transAxes, fontsize=_FONTS["annotation"], va="top",
                        bbox=dict(boxstyle="round", fc="white", ec="black", alpha=0.9))
        ax.set_title(title, fontsize=_FONTS["title"], fontweight="bold")
        ax.set_xlabel("Calcium (z-score)", fontsize=_FONTS["axis"])
        ax.set_ylabel("EEG (z-score)" if ax is ax1 else "", fontsize=_FONTS["axis"])
        ax.set_xlim([xlo, xhi]); ax.set_ylim([ylo, yhi])
        ax.tick_params(labelsize=_FONTS["tick"])
        ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    if save_path:
        _save_fig(fig, save_path, config.plot_formats, config.color_dpi)
    if not config.headless:
        plt.show()
    plt.close(fig)
    return fig, sc, st


# Population-level plotting

def create_population_violin_plot(
    collector: PopulationCorrelationCollector,
    output_dir: str | Path,
    channel: str,
    config: StatsConfig,
) -> tuple[plt.Figure | None, dict]:
    """Violin + individual-points plot comparing control vs treatment for one drug."""
    pop = collector.compute_population_statistics(
        config.bootstrap_iterations, config.confidence_level,
        config.paired_test, config.min_subjects_for_stats,
    )
    if "error" in pop:
        warnings.warn(f"Population plot skipped for {collector.drug_name}: {pop['error']}", stacklevel=2)
        return None, pop

    ctrl, treat = collector.get_arrays()
    fig, ax = plt.subplots(figsize=(_SINGLE_COL, _SINGLE_COL))

    vp_c = ax.violinplot([ctrl[~np.isnan(ctrl)]],   positions=[1],
                         showmeans=False, showmedians=False, showextrema=False)
    vp_t = ax.violinplot([treat[~np.isnan(treat)]], positions=[2],
                         showmeans=False, showmedians=False, showextrema=False)
    for pc, color in [(vp_c["bodies"][0], _POP_COLORS["violin_control"]),
                      (vp_t["bodies"][0], _POP_COLORS["violin_treatment"])]:
        pc.set_facecolor(color); pc.set_edgecolor("black")
        pc.set_linewidth(1);    pc.set_alpha(_POP_COLORS["violin_alpha"])

    np.random.seed(42)
    jc = np.random.normal(0, 0.04, len(ctrl))
    jt = np.random.normal(0, 0.04, len(treat))
    ax.scatter(1 + jc, ctrl,  c=_POP_COLORS["point"], s=_POP_COLORS["point_size"],
               alpha=0.8, zorder=3, edgecolors="white", linewidths=0.5)
    ax.scatter(2 + jt, treat, c=_POP_COLORS["point"], s=_POP_COLORS["point_size"],
               alpha=0.8, zorder=3, edgecolors="white", linewidths=0.5)
    for i in range(len(ctrl)):
        if not (np.isnan(ctrl[i]) or np.isnan(treat[i])):
            ax.plot([1 + jc[i], 2 + jt[i]], [ctrl[i], treat[i]],
                    color=_POP_COLORS["line"], alpha=_POP_COLORS["line_alpha"],
                    linewidth=0.8, zorder=2)

    c_med = pop["control"]["median"]
    t_med = pop["treatment"]["median"]
    ax.hlines(c_med, 0.75, 1.25, colors="black", linewidth=2, zorder=4)
    ax.hlines(t_med, 1.75, 2.25, colors="black", linewidth=2, zorder=4)

    p_val  = pop["comparison"]["p_value"]
    stars  = pop["comparison"]["p_value_str"]
    d_val  = pop["comparison"]["cohens_d"]
    ymax   = max(np.nanmax(ctrl), np.nanmax(treat))
    ymin   = min(np.nanmin(ctrl), np.nanmin(treat))
    yr     = ymax - ymin
    if p_val < 0.05:
        by = ymax + 0.1 * yr
        ax.plot([1, 1, 2, 2], [by, by + 0.03 * yr, by + 0.03 * yr, by], "k-", linewidth=1)
        ax.text(1.5, by + 0.05 * yr, stars, ha="center", va="bottom", fontsize=_FONTS["annotation"])

    ax.set_title(
        f"{_fmt_drug_short(collector.drug_name)}\n"
        f"median: {c_med:.2f}±{pop['control']['std']:.2f} → {t_med:.2f}±{pop['treatment']['std']:.2f}",
        fontsize=_FONTS["title"],
    )
    ax.text(0.98, 0.02,
            f"n={pop['n_valid']}\np={p_val:.4f} ({stars})\nCohen's d={d_val:.2f}",
            transform=ax.transAxes, fontsize=_FONTS["stats"], va="bottom", ha="right",
            bbox=dict(boxstyle="round", fc="white", ec="gray", alpha=0.9))
    ax.set_xticks([1, 2])
    ax.set_xticklabels(["Control", "Treatment"], fontsize=_FONTS["axis"])
    ax.set_ylabel("Pearson Correlation (r)", fontsize=_FONTS["axis"])
    ax.tick_params(axis="y", labelsize=_FONTS["tick"])
    ax.axhline(0, color="gray", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.set_ylim([ymin - 0.15 * yr, ymax + 0.25 * yr]); ax.set_xlim([0.5, 2.5])
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()

    safe_drug = collector.drug_name.replace(":", "_").replace(" ", "_").replace(".", "")
    base = Path(output_dir) / f"population_violin_{safe_drug}_{channel}"
    _save_fig(fig, base, config.plot_formats + ["eps"], config.color_dpi)
    if not config.headless:
        plt.show()
    plt.close(fig)
    return fig, pop


def create_all_drugs_summary_plot(
    all_collectors: dict[str, PopulationCorrelationCollector],
    output_dir: str | Path,
    channel: str,
    config: StatsConfig,
) -> tuple[plt.Figure | None, dict]:
    """Two-panel summary: median correlations + Cohen's d across all drugs."""
    if not all_collectors:
        return None, {}

    all_stats = {d: c.compute_population_statistics(
        config.bootstrap_iterations, config.confidence_level,
        config.paired_test, config.min_subjects_for_stats,
    ) for d, c in all_collectors.items()}

    n_drugs = len(all_collectors)
    drug_names = list(all_collectors.keys())
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(_DOUBLE_COL, _DOUBLE_COL))
    x = np.arange(n_drugs); w = 0.35

    ctrl_meds  = [all_stats[d].get("control",   {}).get("median", float("nan")) for d in drug_names]
    treat_meds = [all_stats[d].get("treatment", {}).get("median", float("nan")) for d in drug_names]
    ctrl_errs  = [all_stats[d].get("control",   {}).get("std",    0.0)          for d in drug_names]
    treat_errs = [all_stats[d].get("treatment", {}).get("std",    0.0)          for d in drug_names]

    ax1.bar(x - w/2, ctrl_meds,  w, yerr=ctrl_errs,  capsize=3, label="Control",
            color=_POP_COLORS["violin_control"],   edgecolor="black", linewidth=1)
    ax1.bar(x + w/2, treat_meds, w, yerr=treat_errs, capsize=3, label="Treatment",
            color=_POP_COLORS["violin_treatment"], edgecolor="black", linewidth=1)
    for i, d in enumerate(drug_names):
        s = all_stats[d]
        if "error" not in s and s["comparison"]["p_value"] < 0.05:
            yp = max(ctrl_meds[i] + ctrl_errs[i], treat_meds[i] + treat_errs[i]) + 0.05
            ax1.text(i, yp, s["comparison"]["p_value_str"], ha="center", fontsize=_FONTS["annotation"])
    ax1.axhline(0, color="gray", linestyle="--", linewidth=0.5)
    ax1.set_ylabel("Median Correlation (r)", fontsize=_FONTS["axis"])
    ax1.set_xticks(x)
    ax1.set_xticklabels([_fmt_drug_short(d) for d in drug_names],
                        fontsize=_FONTS["tick"], rotation=45, ha="right")
    ax1.legend(fontsize=_FONTS["annotation"])
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.set_title("Population Correlations by Drug Condition", fontsize=_FONTS["title"])

    effects = [all_stats[d].get("comparison", {}).get("cohens_d", 0.0) for d in drug_names]
    e_colors = ["#E74C3C" if e > 0 else "#3498DB" for e in effects]
    ax2.bar(x, effects, color=e_colors, edgecolor="black", linewidth=1, alpha=0.7)
    for thr in [0.2, -0.2, 0.5, -0.5, 0.8, -0.8]:
        ax2.axhline(thr, color="gray", linestyle=":", linewidth=0.5, alpha=0.5)
    ax2.axhline(0, color="black", linewidth=1)
    ax2.set_ylabel("Cohen's d (Effect Size)", fontsize=_FONTS["axis"])
    ax2.set_xticks(x)
    ax2.set_xticklabels([_fmt_drug_short(d) for d in drug_names],
                        fontsize=_FONTS["tick"], rotation=45, ha="right")
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.set_title("Effect Size (Treatment vs Control)", fontsize=_FONTS["title"])
    plt.tight_layout()

    base = Path(output_dir) / f"population_all_drugs_summary_{channel}"
    _save_fig(fig, base, config.plot_formats + ["pdf"], config.color_dpi)
    if not config.headless:
        plt.show()
    plt.close(fig)
    return fig, all_stats


# High-level orchestrator

class ScatterAnalysis:
    """High-level orchestrator for per-subject EEG–calcium scatter analyses.

    Args:
        config: :class:`~aceneurotools.config.stats_config.StatsConfig`
            controlling filter, normalization, and output settings.
    """

    def __init__(self, config: StatsConfig | None = None) -> None:
        self.config = config or StatsConfig()

    def run_subject(
        self,
        eeg_signal: np.ndarray,
        calcium_signal: np.ndarray,
        fr: float,
        line_num: int,
        drug: str,
        selections: dict[int, list[list[float]]],
        channel: str,
        output_dir: str | Path,
        collector: PopulationCorrelationCollector | None = None,
    ) -> tuple[bool, dict | None, dict | None]:
        """Run complete single-subject scatter analysis pipeline.

        Steps: NaN handling → slice → filter + trim → global normalise →
        generate 6 plots (scatter×2, hexbin×2, combined×2) → optionally
        accumulate population statistics.

        Args:
            eeg_signal: EEG signal at *fr* Hz.
            calcium_signal: Calcium fluorescence signal at *fr* Hz.
            fr: Sampling rate in Hz.
            line_num: Experiment line number.
            drug: Drug-condition label.
            selections: Time-window dict from StudyMetadata.
            channel: Channel name used in filenames and descriptions.
            output_dir: Root directory for output files.
            collector: If provided, adds this subject's statistics.

        Returns:
            ``(success, control_stats, treatment_stats)``
        """
        if self.config.headless:
            from aceneurotools.shared.plotting import set_backend
            set_backend(headless=True)

        output_dir = Path(output_dir)
        cfg = self.config

        try:
            # NaN handling
            eeg_clean, _      = handle_nans(eeg_signal,    fr, max_gap_seconds=0.5)
            ca_clean,  _      = handle_nans(calcium_signal, fr, max_gap_seconds=0.5)

            # Slice
            ctrl_eeg,   treat_eeg  = slice_signal(eeg_clean,  selections, line_num, fr)
            ctrl_ca,    treat_ca   = slice_signal(ca_clean,   selections, line_num, fr)
            tw_ctrl  = selections[line_num][0]
            tw_treat = selections[line_num][1]

            # Filter + trim
            from aceneurotools.stats.signal_utils import filter_signals
            fe_ctrl,  fc_ctrl  = filter_signals(ctrl_eeg,  ctrl_ca,  fr, [cfg.lowcut, cfg.highcut], cfg.filter_order)
            fe_treat, fc_treat = filter_signals(treat_eeg, treat_ca, fr, [cfg.lowcut, cfg.highcut], cfg.filter_order)
            fe_ctrl  = trim_filter_edges(fe_ctrl,  fr, cfg.edge_trim_seconds)
            fc_ctrl  = trim_filter_edges(fc_ctrl,  fr, cfg.edge_trim_seconds)
            fe_treat = trim_filter_edges(fe_treat, fr, cfg.edge_trim_seconds)
            fc_treat = trim_filter_edges(fc_treat, fr, cfg.edge_trim_seconds)

            # Global z-score normalisation
            ne_ctrl, ne_treat, nc_ctrl, nc_treat, _ = normalize_signals_global(
                fe_ctrl, fe_treat, fc_ctrl, fc_treat
            )

            # Subject output directory
            safe_drug  = drug.replace(":", "_").replace(" ", "_").replace(".", "")
            subj_dir   = output_dir / f"line_{line_num}_{safe_drug}"
            subj_dir.mkdir(parents=True, exist_ok=True)

            # 6 plots
            print(f"\n  [1/6] Control scatter — Line {line_num}")
            create_scatter_plot(
                nc_ctrl, ne_ctrl, line_num, drug, "Control", channel, fr, tw_ctrl, cfg,
                save_path=subj_dir / f"scatter_control_{channel}",
            )
            print("  [2/6] Control hexbin")
            _, ctrl_stats = create_hexbin_plot(
                nc_ctrl, ne_ctrl, line_num, drug, "Control", channel, fr, tw_ctrl, cfg,
                save_path=subj_dir / f"hexbin_control_{channel}",
            )
            print("  [3/6] Treatment scatter")
            create_scatter_plot(
                nc_treat, ne_treat, line_num, drug, "Treatment", channel, fr, tw_treat, cfg,
                save_path=subj_dir / f"scatter_treatment_{channel}",
            )
            print("  [4/6] Treatment hexbin")
            _, treat_stats = create_hexbin_plot(
                nc_treat, ne_treat, line_num, drug, "Treatment", channel, fr, tw_treat, cfg,
                save_path=subj_dir / f"hexbin_treatment_{channel}",
            )
            print("  [5/6] Combined scatter")
            create_combined_scatter_plot(
                nc_ctrl, ne_ctrl, nc_treat, ne_treat,
                line_num, drug, channel, fr, tw_ctrl, tw_treat, cfg,
                save_path=subj_dir / f"scatter_combined_{channel}",
            )
            print("  [6/6] Combined hexbin")
            create_combined_hexbin_plot(
                nc_ctrl, ne_ctrl, nc_treat, ne_treat,
                line_num, drug, channel, fr, tw_ctrl, tw_treat, cfg,
                save_path=subj_dir / f"hexbin_combined_{channel}",
            )

            if collector is not None:
                collector.add_subject(line_num, ctrl_stats, treat_stats)

            return True, ctrl_stats, treat_stats

        except Exception as exc:
            import traceback
            print(f"  ERROR processing line {line_num}: {exc}")
            traceback.print_exc()
            return False, None, None
