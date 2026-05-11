"""
Ephys quick-look demo script.

Usage:
    python -m aceneurotools.ephys.script --project-path /path/to/project --line-num 97

All parameters can be overridden via CLI flags.
"""
import argparse
import logging

from aceneurotools.ephys.channel_worker import ChannelWorker
from aceneurotools.ephys.neuralynx_data_manager import NeuralynxDataManager
from aceneurotools.shared.experiment_data_manager import ExperimentDataManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Ephys quick-look: load a single channel and plot its spectrogram.")
    parser.add_argument("--project-path", required=True, help="Path to project directory containing experiments.csv")
    parser.add_argument("--data-path", default=None, help="Base path for raw experimental data")
    parser.add_argument("--line-num", type=int, default=97, help="Experiment line number in experiments.csv")
    parser.add_argument("--channel", default="PFCLFPvsCBEEG", help="Channel name to load")
    parser.add_argument("--filter-type", default=None, choices=["butter", "fir"], help="Optional filter type")
    parser.add_argument("--filter-range", nargs=2, type=float, default=[0.5, 4], metavar=("LOW", "HIGH"))
    parser.add_argument("--remove-artifacts", action="store_true")
    parser.add_argument("--no-plot-spectrogram", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s: %(message)s")

    experiment_data_manager = ExperimentDataManager(
        args.line_num,
        project_path=args.project_path,
        data_path=args.data_path,
        logging_level=args.log_level.upper(),
    )
    ephys_directory = experiment_data_manager.get_ephys_directory()
    ephys_data_manager = NeuralynxDataManager(
        ephys_directory,
        auto_import_ephys_block=True,
        auto_process_block=False,
    )
    ephys_data_manager.process_ephys_block_to_channels(
        remove_artifacts=args.remove_artifacts,
        channels=[args.channel],
    )

    if args.filter_type:
        ephys_data_manager.filter_ephys(
            args.channel,
            ftype=args.filter_type,
            cut=args.filter_range,
        )

    channel = ephys_data_manager.get_channel(args.channel)
    channel_worker = ChannelWorker(channel)

    if not args.no_plot_spectrogram:
        channel_worker.plot_spectrogram(plot_events=True)


if __name__ == '__main__':
    main()
