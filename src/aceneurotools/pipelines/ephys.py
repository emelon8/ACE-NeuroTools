import argparse
import logging
import sys
import tkinter
from pathlib import Path

from aceneurotools.ephys.channel_worker import ChannelWorker
from aceneurotools.ephys.ephys_data_manager import EphysDataManager
from aceneurotools.ephys.ephys_loader import load_ephys_for_analysis
from aceneurotools.shared.cli_utils import (
    apply_headless_policy,
    build_run_params,
    run_allowed_keys,
    validate_run_params,
)
from aceneurotools.shared.exceptions import (
    AceNeuroError,
    PipelineExecutionError,
    print_cli_error,
)
from aceneurotools.shared.experiment_data_manager import ExperimentDataManager


class EphysPipeline:
    """High-level API for electrophysiology data analysis workflows.

    Provides simplified methods for loading, filtering, and visualizing
    Neuralynx ephys data with configurable analysis parameters.

    Attributes:
        ephys_data_manager: EphysDataManager instance (set after run()).
    """

    ephys_data_manager: EphysDataManager

    def __init__(self) -> None:
        """Initialize the EphysPipeline."""
        pass



    def run(
        self,
        line_num: int,
        project_path: str | Path | None = None,
        data_path: str | Path | None = None,
        channel_name: str = 'PFCLFPvsCBEEG',
        remove_artifacts: bool = False,
        filter_type: str | None = None, # If desired, enter the type, eg "butter"
        filter_range: list[float] = [0.5, 4],
        compute_phases: bool = False,
        plot_channel: bool = False,
        plot_spectrogram: bool = False,
        plot_phases: bool = False,
        logging_level: str | int = "CRITICAL",
        headless: bool = False
    ) -> None:
        """Run the ephys analysis pipeline for a single channel.

        Loads ephys data, optionally filters and computes phases, and
        generates plots based on the provided parameters.

        Args:
            line_num: Experiment line number in experiments.csv.
            project_path: Optional explicit path to project repository.
            data_path: Optional explicit base path for raw experimental data.
            channel_name: Name of ephys channel to analyze.
            remove_artifacts: If True, apply artifact removal.
            filter_type: Filter type ('butter', 'fir') or None to skip.
            filter_range: [low, high] cutoff frequencies for bandpass.
            compute_phases: If True, compute instantaneous phase via Hilbert.
            plot_channel: If True, plot the time-domain signal.
            plot_spectrogram: If True, plot the multitaper spectrogram.
            plot_phases: If True, plot phase distribution histogram.
            logging_level: Logging verbosity ('DEBUG', 'INFO', 'CRITICAL').
            headless: If True, disable GUI and use Agg backend.
        """

        from aceneurotools.shared.plotting import set_backend
        set_backend(headless=headless)
        if headless:
            print("Running in HEADLESS mode. Plotting disabled.", flush=True)
            plot_channel = False
            plot_spectrogram = False
            plot_phases = False
        elif hasattr(tkinter, '_default_root') and tkinter._default_root:
            tkinter._default_root.destroy()

        logger = logging.getLogger(__name__)
        logger.setLevel(logging_level)

        filter_bool = filter_type is not None

        # Delegate all loading logic to the ephys-layer function so that
        # multimodal/ can call that function directly without importing pipelines/.
        self.ephys_data_manager = load_ephys_for_analysis(
            line_num=line_num,
            project_path=project_path,
            data_path=data_path,
            channel_names=[channel_name],
            filter_type=filter_type,
            filter_range=filter_range,
            remove_artifacts=remove_artifacts,
            logging_level=logging_level,
        )

        if compute_phases:
            try:
                self.ephys_data_manager.compute_phases_all_channels()
            except Exception as e:
                raise PipelineExecutionError(
                    "Phase computation failed for ephys data.",
                    stage="compute_phases",
                    line_num=line_num,
                    project_path=project_path,
                    data_path=data_path,
                    hint="Ensure filtered channel data is available before computing phases.",
                ) from e

        logger.info(f"Visualizing channel: {channel_name}")
        try:
            channel = self.ephys_data_manager.get_channel(channel_name)
        except Exception as e:
            raise PipelineExecutionError(
                f"Could not load requested channel '{channel_name}'.",
                stage="get_channel",
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                hint="Confirm channel_name appears in experiment metadata and imported channels.",
            ) from e
        channel_worker = ChannelWorker(channel)

        if plot_channel:
            channel_worker.plot_channel(use_filtered=filter_bool)

        if plot_spectrogram:
            channel_worker.plot_spectrogram(use_filtered=filter_bool, plot_events=False)

        if plot_phases:
            channel_worker.plot_phases()



    def run_all_channels(
        self,
        line_num: int,
        project_path: str | Path | None = None,
        data_path: str | Path | None = None,
        remove_artifacts: bool = False,
        filter_type: str | None = None,
        filter_range: list[float] = [0.5, 4],
        plot_channel: bool = False,
        plot_spectrogram: bool = False,
        logging_level: str | int = "CRITICAL",
        headless: bool = False,
    ) -> None:
        """Run ephys analysis pipeline for all channels in an experiment.

        Iterates through all channels listed in the experiment metadata
        and performs the analysis workflow on each.

        Args:
            line_num: Experiment line number in experiments.csv.
            project_path: Optional explicit path to project repository.
            data_path: Optional explicit base path for raw experimental data.
            remove_artifacts: If True, apply artifact removal.
            filter_type: Filter type ('butter', 'fir') or None to skip.
            filter_range: [low, high] cutoff frequencies for bandpass.
            plot_channel: If True, plot time-domain signals.
            plot_spectrogram: If True, plot spectrograms.
            logging_level: Logging verbosity.
            headless: If True, disable GUI and use Agg backend.
        """
        logger = logging.getLogger(__name__)
        logger.setLevel(logging_level)

        use_filter: bool = filter_type is not None

        experiment_data_manager = ExperimentDataManager(
            line_num,
            project_path=project_path,
            data_path=data_path,
            logging_level=logging_level,
        )

        if experiment_data_manager.metadata is None:
            raise ValueError(f"Metadata could not be loaded for line {line_num}")

        channels_str = experiment_data_manager.metadata.get("LFP and EEG CSCs", "")
        if not channels_str:
            logger.warning(f"No channels found in metadata for line {line_num}")
            return

        # Correctly split the semicolon-separated channel names
        channels_list = [ch.strip() for ch in channels_str.split(";")]

        # Delegate to the optimized multi-channel loader
        self.run_multiple_channels(
            line_num=line_num,
            channel_names=channels_list,
            project_path=project_path,
            data_path=data_path,
            remove_artifacts=remove_artifacts,
            filter_type=filter_type,
            filter_range=filter_range,
            logging_level=logging_level,
            headless=headless,
        )

        # Visualize each channel
        for ch_name in channels_list:
            logger.info(f"Visualizing channel: {ch_name}")
            try:
                channel = self.ephys_data_manager.get_channel(ch_name)
                worker = ChannelWorker(channel)

                if plot_channel:
                    worker.plot_channel(use_filtered=use_filter)
                if plot_spectrogram:
                    worker.plot_spectrogram(use_filtered=use_filter, plot_events=False)
            except Exception as e:
                logger.error(f"Failed to visualize channel {ch_name}: {e}")


    def run_multiple_channels(
        self,
        line_num: int,
        channel_names: list[str],
        project_path: str | Path | None = None,
        data_path: str | Path | None = None,
        remove_artifacts: bool = False,
        filter_type: str | None = None,
        filter_range: list[float] = [0.5, 4],
        logging_level: str | int = "CRITICAL",
        headless: bool = False,
    ) -> None:
        """Run the ephys pipeline loading the recording block exactly once.

        Unlike calling :meth:`run` once per channel (which reads the raw file
        from disk each time), this method loads the ephys block a single time
        and then processes all requested *channel_names* from it.  This is
        critical for multi-GB recordings where repeated :py:meth:`read_block`
        calls dominate wall-clock time.

        After this method returns, every channel in *channel_names* is
        available via ``self.ephys_data_manager.get_channel(name)``.

        Args:
            line_num: Experiment row in ``experiments.csv``.
            channel_names: List of channel names to load and (optionally) filter.
                All names must be present in the recording file.
            project_path: Directory containing ``experiments.csv``.
            data_path: Base directory for raw experimental data.
            remove_artifacts: If ``True``, apply Hann-window artifact removal.
            filter_type: Filter family (``'butter'``, ``'fir'``) or ``None``
                to skip filtering.
            filter_range: ``[low_hz, high_hz]`` bandpass cutoffs.
            logging_level: Python logging level string or integer.
            headless: If ``True``, disable GUI and use the Agg backend.

        Raises:
            :class:`~aceneurotools.shared.exceptions.DataNotFoundError`: If
                experiment metadata files are missing.
            :class:`~aceneurotools.shared.exceptions.PipelineExecutionError`: On
                any loading, processing, or filtering failure.
        """
        from aceneurotools.shared.plotting import set_backend
        set_backend(headless=headless)
        if not headless and hasattr(tkinter, "_default_root") and tkinter._default_root:
            tkinter._default_root.destroy()

        logger = logging.getLogger(__name__)
        logger.setLevel(logging_level)

        # Delegate all loading logic to the ephys-layer function (single disk read).
        self.ephys_data_manager = load_ephys_for_analysis(
            line_num=line_num,
            project_path=project_path,
            data_path=data_path,
            channel_names=channel_names,
            filter_type=filter_type,
            filter_range=filter_range,
            remove_artifacts=remove_artifacts,
            logging_level=logging_level,
        )



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Ephys Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with explicit project path
  python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /path/to/project

  # Run in headless mode (no GUI) for batch processing
  python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /path/to/project --headless
"""
    )
    parser.add_argument('--line-num', type=int, required=True,
                        help="Experiment line number from experiments.csv")
    parser.add_argument('--project-path', type=str, required=True,
                        help="Path to project directory (containing experiments.csv)")
    parser.add_argument('--data-path', type=str,
                        help="Base path for raw experimental data")
    parser.add_argument('--headless', action='store_true',
                        help="Run in headless mode (no GUI)")

    args = parser.parse_args()

    # Default parameters
    defaults = {
        'channel_name': 'PFCLFPvsCBEEG',
        'remove_artifacts': False,
        'filter_type': None,
        'filter_range': [0.3, 0.5],
        'compute_phases': False,
        'plot_channel': True,
        'plot_spectrogram': True,
        'plot_phases': False,
        'logging_level': "DEBUG"
    }

    from aceneurotools.config.config_utils import load_analysis_params
    run_params = build_run_params(
        defaults=defaults,
        allowed_keys=run_allowed_keys(EphysPipeline.run),
        line_num=args.line_num,
        project_path=args.project_path,
        data_path=args.data_path,
        headless=args.headless,
        csv_loader=load_analysis_params,
    )
    apply_headless_policy(pipeline_name="ephys", run_params=run_params)
    validate_run_params(pipeline_name="ephys", run_params=run_params)

    e = EphysPipeline()
    try:
        e.run(**run_params)
    except (AceNeuroError, FileNotFoundError, ValueError) as e:
        print_cli_error(e, include_cause=args.headless)
        if args.headless:
            sys.exit(1)
        raise
