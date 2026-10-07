"""Coherence analysis engine: power, coherence, cross-correlation, and lag between two signals."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from aceneurotools.multimodal.signal_utils import (
    compute_signal_stats,
    filter_signals,
    slice_signal,
)
from aceneurotools.multimodal.stats_config import StatsConfig

# Optional coherogram dependency
try:
    import xarray as xr  # noqa: F401 — availability check for the optional plotting stack
    from xrscipy.signal.spectral import coherogram as _xrs_coherogram

    _HAS_XRSCIPY = True
except ImportError:
    _HAS_XRSCIPY = False


@dataclass
class SubjectCoherenceResult:
    """Power, coherence, XC, and lag for a single subject — control and treatment windows."""

    line_num: int
    drug: str
    control_stats: list[float] = field(default_factory=list)
    treatment_stats: list[float] = field(default_factory=list)
    ratios: list[float] = field(default_factory=list)

    #: Canonical measurement names (same order as stat lists above).
    #: Derived from signal_1_label / signal_2_label passed to run_subject.
    METRIC_NAMES: list[str] = field(
        default_factory=lambda: ["Signal 1 Power", "Signal 2 Power", "Coherence", "XC", "Lag"],
        repr=False,
    )

    def to_dataframe(self) -> pd.DataFrame:
        """Return a long-format DataFrame row for this subject."""
        return pd.DataFrame(
            {
                "line_num": [self.line_num] * len(self.METRIC_NAMES),
                "Measurement": self.METRIC_NAMES,
                "Control": self.control_stats,
                "Treatment": self.treatment_stats,
                "Ratio": self.ratios,
            }
        )


class CoherenceAnalysis:
    """Compute, visualize, and save coherence statistics for one or many subjects."""

    def __init__(self, config: StatsConfig | None = None) -> None:
        self.config = config or StatsConfig()

    def run_subject(
        self,
        signal_1: np.ndarray,
        signal_2: np.ndarray,
        fr: float,
        line_num: int,
        selections: dict[int, list[list[float]]],
        drug: str,
        output_dir: str | Path,
        signal_1_label: str = "Signal 1",
        signal_2_label: str = "Signal 2",
        *,
        plot_coherogram: bool = False,
        plot_spectrogram: bool = False,
        plot_signal_overview: bool = False,
        save_plots: bool = True,
    ) -> SubjectCoherenceResult:
        """Slice, filter, and compute stats for a single subject. Returns control + treatment results."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        freq_range = [self.config.lowcut, self.config.highcut]

        if self.config.headless:
            from aceneurotools.shared.plotting import set_backend

            set_backend(headless=True)

        # optional overview plots
        if plot_signal_overview:
            self._plot_signal_with_slices(signal_1, fr, line_num, selections, signal_1_label, output_dir, drug)
            self._plot_signal_with_slices(signal_2, fr, line_num, selections, signal_2_label, output_dir, drug)

        if plot_spectrogram:
            self._plot_spectrogram(signal_1, fr, line_num, drug, selections, signal_1_label, output_dir)
            self._plot_spectrogram(signal_2, fr, line_num, drug, selections, signal_2_label, output_dir)

        if plot_coherogram:
            self._plot_coherogram(
                signal_1, signal_2, fr, line_num, drug, selections, output_dir, signal_1_label, signal_2_label
            )

        # -- segment and filter --
        ctrl_1, treat_1 = slice_signal(signal_1, selections, line_num, fr)
        ctrl_2, treat_2 = slice_signal(signal_2, selections, line_num, fr)

        filt_ctrl_1, filt_ctrl_2 = filter_signals(ctrl_1, ctrl_2, fr, freq_range, self.config.filter_order)
        filt_treat_1, filt_treat_2 = filter_signals(treat_1, treat_2, fr, freq_range, self.config.filter_order)

        # statistics
        ctrl_stats = compute_signal_stats(
            filt_ctrl_1,
            filt_ctrl_2,
            fr,
            freq_range,
            self.config.spectrogram_window_length,
            self.config.spectrogram_window_step,
            self.config.spectrogram_time_bandwidth,
            self.config.coherence_nperseg_seconds,
        )
        treat_stats = compute_signal_stats(
            filt_treat_1,
            filt_treat_2,
            fr,
            freq_range,
            self.config.spectrogram_window_length,
            self.config.spectrogram_window_step,
            self.config.spectrogram_time_bandwidth,
            self.config.coherence_nperseg_seconds,
        )

        ratios = [(t / c) if abs(c) >= 1e-10 else float("nan") for c, t in zip(ctrl_stats, treat_stats)]

        metric_names = [
            f"{signal_1_label} Power",
            f"{signal_2_label} Power",
            "Coherence",
            "XC",
            "Lag",
        ]
        return SubjectCoherenceResult(
            line_num=line_num,
            drug=drug,
            control_stats=ctrl_stats,
            treatment_stats=treat_stats,
            ratios=ratios,
            METRIC_NAMES=metric_names,
        )

    # Public: population aggregation

    def run_population(
        self,
        results: list[SubjectCoherenceResult],
        drug_groups: dict[str, list[int]],
        output_dir: str | Path,
        channel_label: str = "channel",
    ) -> dict[str, pd.DataFrame]:
        """Aggregate per-subject results by drug group, add Wilcoxon p-values, and write CSVs."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Group results by drug
        drug_rows: dict[str, list[pd.DataFrame]] = {drug: [] for drug in drug_groups}
        for res in results:
            if res.drug in drug_rows:
                drug_rows[res.drug].append(res.to_dataframe())

        summary: dict[str, pd.DataFrame] = {}
        for drug, rows in drug_rows.items():
            if not rows:
                continue
            raw_df = pd.concat(rows, ignore_index=True)
            avg_df = self._compute_mean_std(raw_df)
            avg_df = self._add_p_values(raw_df, avg_df)
            summary[drug] = avg_df
            self.save_results(raw_df, avg_df, output_dir, drug, channel_label)

        return summary

    def save_results(
        self,
        raw_df: pd.DataFrame | None,
        avg_df: pd.DataFrame | None,
        output_dir: str | Path,
        drug_name: str,
        channel_label: str = "channel",
    ) -> None:
        """Write raw and averaged DataFrames to CSV files."""
        safe_drug = _sanitise(drug_name)
        safe_channel = _sanitise(channel_label)
        out = Path(output_dir)

        if raw_df is not None and not raw_df.empty:
            path = out / f"{safe_drug}_{safe_channel}_data.csv"
            raw_df.to_csv(path, index=False)
            print(f"  Saved: {path}")
        if avg_df is not None and not avg_df.empty:
            path = out / f"{safe_drug}_{safe_channel}_avg_data.csv"
            avg_df.to_csv(path, index=False)
            print(f"  Saved: {path}")

    @staticmethod
    def _compute_mean_std(df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate per-measurement mean, std, and ratio."""
        try:
            grp = df.groupby("Measurement")[["Control", "Treatment", "Ratio"]].agg(["mean", "std"]).reset_index()
            # Recalculate ratio of means rather than mean of ratios
            grp[("Ratio", "mean")] = grp[("Treatment", "mean")] / grp[("Control", "mean")]
        except Exception:
            return pd.DataFrame()
        return grp

    @staticmethod
    def _add_p_values(df: pd.DataFrame, avg_df: pd.DataFrame) -> pd.DataFrame:
        """Add Wilcoxon signed-rank p-values to the aggregated DataFrame."""
        if df is None or avg_df is None or df.empty or avg_df.empty:
            return avg_df

        p_map: dict[str, float] = {}
        for measurement, group in df.groupby("Measurement"):
            if str(measurement).lower() == "lag":
                p_map[measurement] = float("nan")
                continue
            ctrl = group["Control"].values
            treat = group["Treatment"].values
            valid = ~(np.isnan(ctrl) | np.isnan(treat))
            ctrl, treat = ctrl[valid], treat[valid]
            if len(ctrl) >= 3:
                try:
                    _, p_val = wilcoxon(ctrl, treat, zero_method="wilcox", correction=False)
                except ValueError:
                    p_val = float("nan")
            else:
                p_val = float("nan")
            p_map[measurement] = float(p_val)

        avg_df["P-value"] = avg_df["Measurement"].map(p_map)
        return avg_df

    # Private: plotting

    def _plot_signal_with_slices(
        self,
        signal: np.ndarray,
        fr: float,
        line_num: int,
        selections: dict[int, list[list[float]]],
        title: str,
        output_dir: Path,
        drug: str,
    ) -> None:
        """Plot full signal with control (blue) and treatment (red) overlaid."""
        windows = selections.get(line_num)
        if windows is None:
            return

        ctrl_seg, treat_seg = slice_signal(signal, selections, line_num, fr)
        samples_per_min = fr * 60.0
        time_full = np.arange(len(signal)) / samples_per_min

        ctrl_start_min = windows[0][0]
        ctrl_end_min = windows[0][1]
        treat_start_min = windows[1][0]
        treat_end_min = windows[1][1]

        time_ctrl = (
            np.arange(int(ctrl_start_min * samples_per_min), int(ctrl_end_min * samples_per_min)) / samples_per_min
        )
        time_treat = (
            np.arange(int(treat_start_min * samples_per_min), int(treat_end_min * samples_per_min)) / samples_per_min
        )

        # Clamp to signal length
        time_ctrl = time_ctrl[: len(ctrl_seg)]
        time_treat = time_treat[: len(treat_seg)]

        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(time_full, signal, color="gray", alpha=0.5, linewidth=0.5)
        ax.plot(time_ctrl, ctrl_seg, color="blue", linewidth=1.5, label="Control")
        ax.plot(time_treat, treat_seg, color="red", linewidth=1.5, label="Treatment")
        ax.set_xlabel("Time (minutes)", fontsize=12)
        ax.set_ylabel("Amplitude", fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        safe_title = _sanitise(title)
        safe_drug = _sanitise(drug)
        for fmt in self.config.plot_formats:
            path = output_dir / f"signal_{safe_title}_{safe_drug}_line{line_num}.{fmt}"
            _save_figure(fig, path, self.config.color_dpi)

        if not self.config.headless:
            plt.show()
        plt.close(fig)

    def _plot_spectrogram(
        self,
        signal: np.ndarray,
        fr: float,
        line_num: int,
        drug: str,
        selections: dict[int, list[list[float]]],
        title: str,
        output_dir: Path,
    ) -> None:
        """Plot multitaper spectrogram with control / treatment markers."""
        from aceneurotools.shared.multitaper_spectrogram_python import multitaper_spectrogram

        num_tapers = int(self.config.spectrogram_time_bandwidth * 2 - 1)
        try:
            power_matrix, times, freqs = multitaper_spectrogram(
                signal,
                fr,
                frequency_range=self.config.spectrogram_freq_lims,
                time_bandwidth=self.config.spectrogram_time_bandwidth,
                num_tapers=num_tapers,
                window_params=[self.config.spectrogram_window_length, self.config.spectrogram_window_step],
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
        except Exception as exc:
            warnings.warn(f"Spectrogram failed for line {line_num}: {exc}", stacklevel=2)
            return

        power_db = 10.0 * np.log10(power_matrix + 1e-30)
        times_min = times / 60.0

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.imshow(
            power_db,
            aspect="auto",
            origin="lower",
            extent=[times_min[0], times_min[-1], freqs[0], freqs[-1]],
            vmin=np.percentile(power_db, 5),
            vmax=np.percentile(power_db, 95),
        )
        # Mark control / treatment windows
        windows = selections.get(line_num)
        if windows:
            _mark_windows(ax, windows)
        ax.set_xlabel("Time (minutes)", fontsize=12)
        ax.set_ylabel("Frequency (Hz)", fontsize=12)
        ax.set_title(f"{title} — Line {line_num} | {drug}", fontsize=10)
        plt.tight_layout()

        safe_title = _sanitise(title)
        safe_drug = _sanitise(drug)
        for fmt in self.config.plot_formats:
            path = output_dir / f"spectrogram_{safe_title}_{safe_drug}_line{line_num}.{fmt}"
            _save_figure(fig, path, self.config.color_dpi)

        if not self.config.headless:
            plt.show()
        plt.close(fig)

    def _plot_coherogram(
        self,
        signal_1: np.ndarray,
        signal_2: np.ndarray,
        fr: float,
        line_num: int,
        drug: str,
        selections: dict[int, list[list[float]]],
        output_dir: Path,
        signal_1_label: str = "Signal 1",
        signal_2_label: str = "Signal 2",
    ) -> None:
        """Plot time-frequency coherogram (requires ``xrscipy``)."""
        if not _HAS_XRSCIPY:
            warnings.warn(
                "xrscipy is not installed — coherogram plot skipped.  Install with: pip install xrscipy",
                stacklevel=2,
            )
            return

        import xarray as xr  # noqa: F401 — availability check for the optional plotting stack

        wl = self.config.coherogram_window_length
        step = self.config.coherogram_window_step
        overlap_ratio = 1.0 - (step / wl)
        times_min = np.arange(len(signal_1)) / (fr * 60.0)

        da1 = xr.DataArray(signal_1, dims=["time"], coords={"time": times_min})
        da2 = xr.DataArray(signal_2, dims=["time"], coords={"time": times_min})

        try:
            coh = _xrs_coherogram(
                da1,
                da2,
                fs=fr,
                seglen=wl,
                overlap_ratio=overlap_ratio,
                nrolling=self.config.coherogram_nrolling,
                window="hann",
            )
            coh["time"] = coh["time"] / 60.0
        except Exception as exc:
            warnings.warn(f"Coherogram computation failed: {exc}", stacklevel=2)
            return

        coh_sq = abs(coh) ** 2
        coh_sq.plot.imshow(cmap="viridis", robust=False, vmin=0, vmax=0.7, figsize=(10, 6))
        fig = plt.gcf()
        ax = plt.gca()

        windows = selections.get(line_num)
        if windows:
            _mark_windows(ax, windows)

        ax.set_xlabel("Time (minutes)", fontsize=14)
        ax.set_ylabel("Frequency (Hz)", fontsize=14)
        ax.set_title(
            f"Coherogram: {signal_1_label} vs {signal_2_label} — Line {line_num} | {drug}",
            fontsize=12,
        )
        plt.tight_layout()

        safe_s1 = _sanitise(signal_1_label)
        safe_s2 = _sanitise(signal_2_label)
        safe_drug = _sanitise(drug)
        for fmt in self.config.plot_formats:
            path = output_dir / f"coherogram_{safe_s1}_vs_{safe_s2}_{safe_drug}_line{line_num}.{fmt}"
            _save_figure(fig, path, self.config.color_dpi)

        if not self.config.headless:
            plt.show()
        plt.close(fig)


# Module-level helpers


def _sanitise(name: str) -> str:
    """Replace filesystem-unsafe characters with underscores."""
    for ch in (":", " ", "/", "\\", "."):
        name = name.replace(ch, "_")
    return name


def _save_figure(fig: plt.Figure, path: Path, dpi: int) -> None:
    """Save *fig* to *path*, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict = {"dpi": dpi, "bbox_inches": "tight"}
    if str(path).endswith(".tiff") or str(path).endswith(".tif"):
        kwargs["pil_kwargs"] = {"compression": "tiff_lzw"}
    try:
        fig.savefig(str(path), **kwargs)
    except Exception as exc:
        warnings.warn(f"Could not save figure to {path}: {exc}", stacklevel=2)


def _mark_windows(ax: plt.Axes, windows: list[list[float]]) -> None:
    """Add vertical lines marking control (red dashed) and treatment (orange dashed)."""
    w = 0.5
    ctrl_color = "red"
    treat_color = "orange"
    for start, end in [windows[0]]:
        ax.axvline(x=start, color=ctrl_color, linestyle="--", linewidth=w)
        ax.axvline(x=end, color=ctrl_color, linestyle="--", linewidth=w)
    for start, end in [windows[1]]:
        ax.axvline(x=start, color=treat_color, linestyle="--", linewidth=w)
        ax.axvline(x=end, color=treat_color, linestyle="--", linewidth=w)
