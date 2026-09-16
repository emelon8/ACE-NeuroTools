"""Statistical analysis pipeline for ACE-Neuro."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import traceback
import warnings
from datetime import datetime
from pathlib import Path

from aceneurotools.config.lab_config import LabConfig
from aceneurotools.config.stats_config import StatsConfig, StudyMetadata
from aceneurotools.shared.exceptions import AceNeuroError, PipelineExecutionError, print_cli_error
from aceneurotools.stats.coherence_analysis import CoherenceAnalysis, SubjectCoherenceResult
from aceneurotools.stats.loader import (
    load_calcium_signal,
    load_for_stats,
    load_for_stats_two_channels,
)
from aceneurotools.stats.scatter_analysis import PopulationCorrelationCollector, ScatterAnalysis
from aceneurotools.stats.signal_utils import slice_signal  # noqa: F401 — re-exported for convenience

VALID_ANALYSES: dict[str, str] = {
    "coherence_ephys_calcium": (
        "Spectral power, Welch coherence, and cross-correlation between an "
        "ephys channel and the mean-fluorescence calcium signal."
    ),
    "coherence_ephys_ephys": (
        "Spectral power, Welch coherence, and cross-correlation between two "
        "ephys channels from the same recording."
    ),
    "scatter_correlation": (
        "Pearson r scatter plots (EEG vs calcium), autocorrelation-corrected "
        "significance, Fisher-z CIs, and population violin plots."
    ),
}

_ANALYSIS_KEYS = list(VALID_ANALYSES.keys())


class _RunLog:
    """Accumulates per-subject outcomes and writes run_log.json at the end of each run."""

    def __init__(
        self,
        analyses: list[str],
        subjects: list[int],
        lab_config_path: str | Path | None,
        stats_config_path: str | Path | None,
        params: dict,
    ) -> None:
        self.run_timestamp: str = datetime.now().isoformat(timespec="seconds")
        self.analyses_requested: list[str] = list(analyses)
        self.subjects_requested: list[int] = list(subjects)
        self.lab_config_path: str | None = str(lab_config_path) if lab_config_path else None
        self.stats_config_path: str | None = str(stats_config_path) if stats_config_path else None
        self.params: dict = params
        self.completed: list[dict] = []
        self.skipped: list[dict] = []

    def record_complete(self, line_num: int, analysis: str) -> None:
        self.completed.append({"line_num": line_num, "analysis": analysis})

    def record_skip(self, line_num: int, analysis: str, exc: Exception) -> None:
        entry: dict = {
            "line_num": line_num,
            "analysis": analysis,
            "reason": str(exc),
        }
        if isinstance(exc, AceNeuroError):
            ctx = exc.context
            if ctx.stage:
                entry["stage"] = ctx.stage
            if ctx.hint:
                entry["hint"] = ctx.hint
        self.skipped.append(entry)

    def write(self, path: Path) -> None:
        payload = {
            "run_timestamp": self.run_timestamp,
            "analyses_requested": self.analyses_requested,
            "subjects_requested": self.subjects_requested,
            "lab_config_path": self.lab_config_path,
            "stats_config_path": self.stats_config_path,
            "params": self.params,
            "completed": self.completed,
            "skipped": self.skipped,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            json.dump(payload, fh, indent=2)

    def print_summary(self, log_path: Path) -> None:
        completed_subjects = sorted({e["line_num"] for e in self.completed})
        skipped_subjects = sorted({e["line_num"] for e in self.skipped})
        print(
            f"\nRun complete: {len(completed_subjects)} subject(s) completed, "
            f"{len(skipped_subjects)} skipped."
        )
        if skipped_subjects:
            for entry in self.skipped:
                print(
                    f"  Skipped: line {entry['line_num']} "
                    f"({entry['analysis']}) — {entry['reason']}"
                )
            print(f"  Full details: {log_path}")


class StatsPipeline:
    """Orchestrates statistical analyses across experiments."""

    def __init__(self) -> None:
        self.coherence_results: dict[int, SubjectCoherenceResult] = {}
        self.scatter_collectors: dict[str, PopulationCorrelationCollector] = {}
        self.run_log: _RunLog | None = None
        self._run_log: _RunLog | None = None  # populated during run()

    def run(
        self,
        project_path: str | Path,
        data_path: str | Path | None = None,
        output_dir: str | Path | None = None,
        calcium_signal_dir: str | Path | None = None,
        analyses: list[str] | None = None,
        line_nums: list[int] | None = None,
        channel: str | None = None,
        channel_2: str | None = None,
        freq_range: list[float] | None = None,
        stats_config: StatsConfig | None = None,
        study_metadata: StudyMetadata | None = None,
        lab_config: LabConfig | None = None,
        headless: bool = False,
        verbose: bool = False,
        run_log_path: str | Path | None = None,
        lab_config_path: str | Path | None = None,
        stats_config_path: str | Path | None = None,
    ) -> None:
        """Run the statistical analysis pipeline."""
        from aceneurotools.shared.plotting import set_backend
        set_backend(headless=headless)
        config = stats_config or StatsConfig()
        if headless:
            config.headless = True

        # Resolve study metadata: study_metadata > lab_config > error
        if study_metadata is not None:
            meta = study_metadata
        elif lab_config is not None:
            meta = lab_config.to_study_metadata()
        else:
            StudyMetadata.default()  # always raises ConfigurationError
            return  # unreachable; satisfies type-checkers

        # Resolve channel names: explicit arg > lab_config > hardcoded fallback
        effective_channel: str = (
            channel
            if channel is not None
            else (lab_config.primary_channel if lab_config is not None else "CBvsPCEEG")
        )
        effective_channel_2: str = (
            channel_2
            if channel_2 is not None
            else (
                lab_config.secondary_channel
                if lab_config is not None and lab_config.secondary_channel is not None
                else "PFCEEGvsCBEEG"
            )
        )

        # Resolve frequency range: explicit arg > lab_config > config defaults
        effective_freq_range: list[float] = (
            freq_range
            if freq_range is not None
            else (
                lab_config.freq_range
                if lab_config is not None
                else [config.lowcut, config.highcut]
            )
        )

        project_path = Path(project_path)
        data_path = Path(data_path) if data_path is not None else None
        output_dir = (
            Path(output_dir)
            if output_dir is not None
            else project_path / "stats_results"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        effective_run_log_path = (
            Path(run_log_path) if run_log_path is not None else output_dir / "run_log.json"
        )

        subjects = line_nums if line_nums else meta.all_line_nums()

        selected = _resolve_analyses(analyses)
        if not selected:
            return  # user chose to exit the interactive menu

        print(f"\nRunning analyses: {', '.join(selected)}")
        print(f"Subjects ({len(subjects)}): {subjects}")
        print(
            f"Channel: {effective_channel}  |  "
            f"Freq range: {effective_freq_range} Hz"
        )
        print(f"Output: {output_dir}\n")

        params: dict = {
            "primary_channel": effective_channel,
            "secondary_channel": effective_channel_2,
            "freq_range_hz": effective_freq_range,
            "stats_config": dataclasses.asdict(config),
            "conditions": {
                drug_label: line_nums_list
                for drug_label, line_nums_list in meta.drug_groups.items()
            },
            "time_windows": {
                str(k): v for k, v in meta.selections.items()
            },
            "project_path": str(project_path),
            "output_dir": str(output_dir),
            "calcium_signal_dir": str(calcium_signal_dir) if calcium_signal_dir else None,
            "data_path": str(data_path) if data_path else None,
        }

        self._run_log = _RunLog(
            analyses=selected,
            subjects=subjects,
            lab_config_path=lab_config_path,
            stats_config_path=stats_config_path,
            params=params,
        )

        if "coherence_ephys_calcium" in selected:
            self._run_coherence_ephys_calcium(
                subjects=subjects,
                meta=meta,
                config=config,
                project_path=project_path,
                data_path=data_path,
                output_dir=output_dir / "coherence_ephys_calcium",
                calcium_signal_dir=calcium_signal_dir,
                channel=effective_channel,
                freq_range=effective_freq_range,
                verbose=verbose,
            )

        if "coherence_ephys_ephys" in selected:
            self._run_coherence_ephys_ephys(
                subjects=subjects,
                meta=meta,
                config=config,
                project_path=project_path,
                data_path=data_path,
                output_dir=output_dir / "coherence_ephys_ephys",
                channel=effective_channel,
                channel_2=effective_channel_2,
                freq_range=effective_freq_range,
                verbose=verbose,
            )

        if "scatter_correlation" in selected:
            self._run_scatter_correlation(
                subjects=subjects,
                meta=meta,
                config=config,
                project_path=project_path,
                data_path=data_path,
                output_dir=output_dir / "scatter_correlation",
                calcium_signal_dir=calcium_signal_dir,
                channel=effective_channel,
                freq_range=effective_freq_range,
                verbose=verbose,
            )

        self.run_log = self._run_log
        self._run_log.write(effective_run_log_path)
        self._run_log.print_summary(effective_run_log_path)

    # coherence_ephys_calcium

    def _run_coherence_ephys_calcium(
        self,
        subjects: list[int],
        meta: StudyMetadata,
        config: StatsConfig,
        project_path: Path,
        data_path: Path | None,
        output_dir: Path,
        calcium_signal_dir: str | Path | None,
        channel: str,
        freq_range: list[float],
        verbose: bool,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        engine = CoherenceAnalysis(config)
        all_results: list[SubjectCoherenceResult] = []
        analysis_name = "coherence_ephys_calcium"

        for line_num in subjects:
            drug = meta.drug_of(line_num) or "unknown"
            _print_subject_header(line_num, drug, analysis_name, verbose)

            try:
                ch, miniscope_dm, fr = load_for_stats(
                    line_num=line_num,
                    project_path=project_path,
                    data_path=data_path,
                    channel_name=channel,
                    freq_range=freq_range,
                )
            except PipelineExecutionError as exc:
                _warn_skip(line_num, exc, verbose)
                assert self._run_log is not None
                self._run_log.record_skip(line_num, analysis_name, exc)
                continue

            if calcium_signal_dir is None:
                msg = "--calcium-signal-dir not provided"
                print(f"  [line {line_num}] SKIPPED — {msg}.")
                assert self._run_log is not None
                self._run_log.record_skip(
                    line_num, analysis_name, ValueError(msg)
                )
                continue

            calcium = load_calcium_signal(miniscope_dm, calcium_signal_dir, line_num)
            if calcium is None:
                msg = "Calcium signal file not found"
                print(f"  [line {line_num}] SKIPPED — {msg}.")
                assert self._run_log is not None
                self._run_log.record_skip(
                    line_num, analysis_name, FileNotFoundError(msg)
                )
                continue

            subj_dir = output_dir / f"line_{line_num}"
            subj_dir.mkdir(parents=True, exist_ok=True)

            try:
                result = engine.run_subject(
                    signal_1=ch.signal,
                    signal_2=calcium,
                    fr=fr,
                    line_num=line_num,
                    selections=meta.selections,
                    drug=drug,
                    output_dir=subj_dir,
                    signal_1_label=channel,
                    signal_2_label="CaImaging",
                )
            except Exception as exc:
                _warn_skip(line_num, exc, verbose)
                assert self._run_log is not None
                self._run_log.record_skip(line_num, analysis_name, exc)
                continue

            self.coherence_results[line_num] = result
            all_results.append(result)
            assert self._run_log is not None
            self._run_log.record_complete(line_num, analysis_name)

        if all_results:
            try:
                engine.run_population(
                    results=all_results,
                    drug_groups=meta.drug_groups,
                    output_dir=output_dir,
                    channel_label=channel,
                )
            except Exception as exc:
                print(f"  [population] {analysis_name} summary failed: {exc}")

    # coherence_ephys_ephys

    def _run_coherence_ephys_ephys(
        self,
        subjects: list[int],
        meta: StudyMetadata,
        config: StatsConfig,
        project_path: Path,
        data_path: Path | None,
        output_dir: Path,
        channel: str,
        channel_2: str,
        freq_range: list[float],
        verbose: bool,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        engine = CoherenceAnalysis(config)
        all_results: list[SubjectCoherenceResult] = []
        analysis_name = "coherence_ephys_ephys"

        for line_num in subjects:
            drug = meta.drug_of(line_num) or "unknown"
            _print_subject_header(line_num, drug, analysis_name, verbose)

            try:
                ch1, ch2, _miniscope_dm, fr = load_for_stats_two_channels(
                    line_num=line_num,
                    project_path=project_path,
                    data_path=data_path,
                    channel_name_1=channel,
                    channel_name_2=channel_2,
                    freq_range=freq_range,
                )
            except PipelineExecutionError as exc:
                _warn_skip(line_num, exc, verbose)
                assert self._run_log is not None
                self._run_log.record_skip(line_num, analysis_name, exc)
                continue

            subj_dir = output_dir / f"line_{line_num}"
            subj_dir.mkdir(parents=True, exist_ok=True)

            try:
                result = engine.run_subject(
                    signal_1=ch1.signal,
                    signal_2=ch2.signal,
                    fr=fr,
                    line_num=line_num,
                    selections=meta.selections,
                    drug=drug,
                    output_dir=subj_dir,
                    signal_1_label=channel,
                    signal_2_label=channel_2,
                )
            except Exception as exc:
                _warn_skip(line_num, exc, verbose)
                assert self._run_log is not None
                self._run_log.record_skip(line_num, analysis_name, exc)
                continue

            self.coherence_results[line_num] = result
            all_results.append(result)
            assert self._run_log is not None
            self._run_log.record_complete(line_num, analysis_name)

        if all_results:
            try:
                engine.run_population(
                    results=all_results,
                    drug_groups=meta.drug_groups,
                    output_dir=output_dir,
                    channel_label=f"{channel}_vs_{channel_2}",
                )
            except Exception as exc:
                print(f"  [population] {analysis_name} summary failed: {exc}")

    # scatter_correlation

    def _run_scatter_correlation(
        self,
        subjects: list[int],
        meta: StudyMetadata,
        config: StatsConfig,
        project_path: Path,
        data_path: Path | None,
        output_dir: Path,
        calcium_signal_dir: str | Path | None,
        channel: str,
        freq_range: list[float],
        verbose: bool,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        engine = ScatterAnalysis(config)
        analysis_name = "scatter_correlation"

        collectors: dict[str, PopulationCorrelationCollector] = {
            drug: PopulationCorrelationCollector(drug)
            for drug in meta.drug_groups
        }

        for line_num in subjects:
            drug = meta.drug_of(line_num) or "unknown"
            _print_subject_header(line_num, drug, analysis_name, verbose)

            try:
                ch, miniscope_dm, fr = load_for_stats(
                    line_num=line_num,
                    project_path=project_path,
                    data_path=data_path,
                    channel_name=channel,
                    freq_range=freq_range,
                )
            except PipelineExecutionError as exc:
                _warn_skip(line_num, exc, verbose)
                assert self._run_log is not None
                self._run_log.record_skip(line_num, analysis_name, exc)
                continue

            if calcium_signal_dir is None:
                msg = "--calcium-signal-dir not provided"
                print(f"  [line {line_num}] SKIPPED — {msg}.")
                assert self._run_log is not None
                self._run_log.record_skip(
                    line_num, analysis_name, ValueError(msg)
                )
                continue

            calcium = load_calcium_signal(miniscope_dm, calcium_signal_dir, line_num)
            if calcium is None:
                msg = "Calcium signal file not found"
                print(f"  [line {line_num}] SKIPPED — {msg}.")
                assert self._run_log is not None
                self._run_log.record_skip(
                    line_num, analysis_name, FileNotFoundError(msg)
                )
                continue

            subj_dir = output_dir / f"line_{line_num}"
            subj_dir.mkdir(parents=True, exist_ok=True)

            collector = collectors.get(drug)

            try:
                engine.run_subject(
                    eeg_signal=ch.signal,
                    calcium_signal=calcium,
                    fr=fr,
                    line_num=line_num,
                    drug=drug,
                    selections=meta.selections,
                    channel=channel,
                    output_dir=subj_dir,
                    collector=collector,
                )
            except Exception as exc:
                _warn_skip(line_num, exc, verbose)
                assert self._run_log is not None
                self._run_log.record_skip(line_num, analysis_name, exc)
                continue

            assert self._run_log is not None
            self._run_log.record_complete(line_num, analysis_name)

        self.scatter_collectors = {
            drug: col for drug, col in collectors.items() if col.has_data()
        }
        if self.scatter_collectors:
            from aceneurotools.stats.scatter_analysis import (
                create_all_drugs_summary_plot,
                create_population_violin_plot,
            )
            for drug, col in self.scatter_collectors.items():
                try:
                    create_population_violin_plot(
                        collector=col,
                        output_dir=output_dir,
                        channel=channel,
                        config=config,
                    )
                except Exception as exc:
                    print(f"  [population] violin plot for '{drug}' failed: {exc}")
            try:
                create_all_drugs_summary_plot(
                    all_collectors=list(self.scatter_collectors.values()),
                    output_dir=output_dir,
                    channel=channel,
                    config=config,
                )
            except Exception as exc:
                print(f"  [population] all-drugs summary plot failed: {exc}")


# Module-level helpers

def _print_subject_header(line_num: int, drug: str, analysis: str, verbose: bool) -> None:
    if verbose:
        print(f"  [{analysis}] line {line_num} ({drug})")


def _warn_skip(line_num: int, exc: Exception, verbose: bool = False) -> None:
    print(f"  [line {line_num}] SKIPPED — {type(exc).__name__}: {exc}")
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        print(f"    └── {type(cause).__name__}: {cause}")
    if verbose:
        traceback.print_exc()


def _resolve_analyses(analyses: list[str] | None) -> list[str]:
    """Return a validated list of analysis keys.

    If *analyses* is ``None`` or empty, present an interactive numbered menu.
    Returns an empty list only when the user actively chooses to quit.
    """
    if analyses:
        invalid = [a for a in analyses if a not in VALID_ANALYSES]
        if invalid:
            print(
                f"Unknown analysis type(s): {invalid}\n"
                f"Valid options: {_ANALYSIS_KEYS}"
            )
            sys.exit(1)
        return list(analyses)

    return _interactive_menu()


def _interactive_menu() -> list[str]:
    """Print a numbered menu and return the user-selected analysis keys."""
    print("\n" + "=" * 60)
    print("  ACE-Neuro Statistical Analysis Pipeline")
    print("=" * 60)
    print("\nAvailable analyses:\n")
    for i, (key, description) in enumerate(VALID_ANALYSES.items(), start=1):
        print(f"  {i}. {key}")
        print(f"     {description}\n")
    print("  a. Run ALL analyses")
    print("  q. Quit\n")

    raw = input("Select analyses (e.g. 1 2, or a, or q): ").strip().lower()

    if raw in ("q", "quit", "exit"):
        print("Exiting.")
        return []

    if raw in ("a", "all"):
        return list(VALID_ANALYSES.keys())

    selected: list[str] = []
    for token in raw.split():
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(_ANALYSIS_KEYS):
                selected.append(_ANALYSIS_KEYS[idx])
            else:
                print(f"  Ignoring out-of-range selection: {token}")
        elif token in VALID_ANALYSES:
            selected.append(token)
        else:
            print(f"  Ignoring unrecognised token: {token}")

    seen: set[str] = set()
    unique: list[str] = []
    for a in selected:
        if a not in seen:
            seen.add(a)
            unique.append(a)

    if not unique:
        print("No valid analyses selected.")
    return unique


# CLI

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m aceneurotools.pipelines.stats",
        description=(
            "Run statistical analyses (coherence, scatter/correlation) across "
            "experiments defined in experiments.csv."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # First-time setup: generate config templates for your lab
  python -m aceneurotools.init --project-path /data/project

  # Non-interactive with lab config
  python -m aceneurotools.pipelines.stats \\
      --project-path /data/project \\
      --data-path /data/raw \\
      --output-dir /data/results \\
      --calcium-signal-dir /data/meanFluorescence \\
      --lab-config /data/project/lab_config.json \\
      --analyses coherence_ephys_calcium scatter_correlation

  # Override channel for a single run
  python -m aceneurotools.pipelines.stats \\
      --project-path /data/project \\
      --lab-config /data/project/lab_config.json \\
      --channel MyCustomChannel \\
      --analyses coherence_ephys_calcium

  # Single subject, headless
  python -m aceneurotools.pipelines.stats \\
      --project-path /data/project \\
      --lab-config /data/project/lab_config.json \\
      --line-nums 97 \\
      --analyses scatter_correlation \\
      --headless
""",
    )

    parser.add_argument(
        "--project-path",
        required=True,
        metavar="PATH",
        help="Directory containing experiments.csv.",
    )
    parser.add_argument(
        "--data-path",
        metavar="PATH",
        help="Base directory for raw data.  Uses experiments.csv value when omitted.",
    )
    parser.add_argument(
        "--output-dir",
        metavar="PATH",
        help="Root output directory.  Defaults to <project-path>/stats_results.",
    )
    parser.add_argument(
        "--calcium-signal-dir",
        metavar="PATH",
        help="Directory containing meanFluorescence_<line_num>.npz files.",
    )

    # Configuration files
    config_group = parser.add_argument_group("configuration files")
    config_group.add_argument(
        "--lab-config",
        metavar="PATH",
        help=(
            "Path to lab_config.json (channel names, freq range, study design). "
            "Generate a template with: python -m aceneurotools.init"
        ),
    )
    config_group.add_argument(
        "--stats-config-path",
        metavar="PATH",
        help="Path to stats_config.json (algorithm parameters).  "
             "Uses built-in defaults when omitted.",
    )
    config_group.add_argument(
        "--stats-metadata-path",
        metavar="PATH",
        help=(
            "[DEPRECATED] Use --lab-config instead.  "
            "JSON file produced by StudyMetadata.to_json()."
        ),
    )

    # Analysis selection
    analysis_group = parser.add_argument_group("analysis selection")
    analysis_group.add_argument(
        "--analyses",
        nargs="+",
        metavar="ANALYSIS",
        choices=list(VALID_ANALYSES.keys()),
        help=(
            f"One or more analyses to run: {_ANALYSIS_KEYS}.  "
            "Omit to select interactively."
        ),
    )
    analysis_group.add_argument(
        "--line-nums",
        nargs="+",
        type=int,
        metavar="N",
        help="Explicit experiment line numbers.  Defaults to all subjects in lab_config.json.",
    )

    # Signal parameters (override lab_config values when supplied)
    signal_group = parser.add_argument_group(
        "signal parameters (override lab_config.json when supplied)"
    )
    signal_group.add_argument(
        "--channel",
        default=None,
        metavar="NAME",
        help="Primary ephys channel name.  Overrides primary_channel in lab_config.json.",
    )
    signal_group.add_argument(
        "--channel-2",
        default=None,
        metavar="NAME",
        help=(
            "Second ephys channel for coherence_ephys_ephys.  "
            "Overrides secondary_channel in lab_config.json."
        ),
    )
    signal_group.add_argument(
        "--freq-range",
        nargs=2,
        type=float,
        metavar=("LOW", "HIGH"),
        help="Bandpass filter cutoffs in Hz.  Overrides freq_range in lab_config.json.",
    )

    # Output / runtime
    runtime_group = parser.add_argument_group("runtime options")
    runtime_group.add_argument(
        "--run-log-path",
        metavar="PATH",
        help="Override location for run_log.json.  "
             "Defaults to <output-dir>/run_log.json.",
    )
    runtime_group.add_argument(
        "--headless",
        action="store_true",
        help="Disable GUI; use matplotlib Agg backend (for HPC/batch jobs).",
    )
    runtime_group.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-subject progress messages.",
    )

    return parser


if __name__ == "__main__":
    parser = _build_parser()
    args = parser.parse_args()

    # Load algorithm config
    stats_config: StatsConfig | None = None
    if args.stats_config_path:
        try:
            stats_config = StatsConfig.from_json(args.stats_config_path)
        except Exception as exc:
            print(f"ERROR loading stats config from {args.stats_config_path}: {exc}")
            sys.exit(1)

    # Load lab config (preferred) or fall back to deprecated metadata path
    lab_config: LabConfig | None = None
    study_metadata: StudyMetadata | None = None

    if args.lab_config:
        try:
            lab_config = LabConfig.from_json(args.lab_config)
        except Exception as exc:
            print(f"ERROR loading lab config from {args.lab_config}: {exc}")
            sys.exit(1)
    elif args.stats_metadata_path:
        warnings.warn(
            "--stats-metadata-path is deprecated and will be removed in a future "
            "release.  Use --lab-config with a lab_config.json file instead.\n"
            "Run 'python -m aceneurotools.init --project-path <dir>' to generate "
            "a lab_config.json template.",
            DeprecationWarning,
            stacklevel=1,
        )
        try:
            study_metadata = StudyMetadata.from_json(args.stats_metadata_path)
        except Exception as exc:
            print(
                f"ERROR loading study metadata from {args.stats_metadata_path}: {exc}"
            )
            sys.exit(1)
    # If neither is provided, StudyMetadata.default() will raise inside run().

    # Resolve output dir early so run_log_path has a sensible default.
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else Path(args.project_path) / "stats_results"
    )

    pipeline = StatsPipeline()

    # Propagate path metadata into the run log after construction.
    try:
        pipeline.run(
            project_path=args.project_path,
            data_path=args.data_path,
            output_dir=output_dir,
            calcium_signal_dir=args.calcium_signal_dir,
            analyses=args.analyses,
            line_nums=args.line_nums,
            channel=args.channel,
            channel_2=args.channel_2,
            freq_range=args.freq_range,
            stats_config=stats_config,
            study_metadata=study_metadata,
            lab_config=lab_config,
            headless=args.headless,
            verbose=args.verbose,
            run_log_path=args.run_log_path,
            lab_config_path=args.lab_config,
            stats_config_path=args.stats_config_path,
        )
    except (AceNeuroError, FileNotFoundError, ValueError) as exc:
        print_cli_error(exc, include_cause=args.headless)
        if args.headless:
            sys.exit(1)
        raise
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
