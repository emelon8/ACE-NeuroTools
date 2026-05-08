from aceneurotools.ephys.channel_worker import ChannelWorker
from aceneurotools.ephys.ephys_data_manager import EphysDataManager
from aceneurotools.ephys.rhs2116_data_manager import RHS2116DataManager
from aceneurotools.ephys.neuralynx_data_manager import NeuralynxDataManager
from aceneurotools.ephys.visualizer import Visualizer
from aceneurotools.shared.experiment_data_manager import ExperimentDataManager
from typing import List, Optional, Union, Dict, Any
from pathlib import Path
from aceneurotools.shared import file_downloader
import logging
import argparse
import sys
import matplotlib
import tkinter
from aceneurotools.shared.exceptions import (
    AceNeuroError,
    DataNotFoundError,
    PipelineExecutionError,
    print_cli_error,
)
from aceneurotools.shared.cli_utils import (
    apply_headless_policy,
    build_run_params,
    run_allowed_keys,
    validate_run_params,
)



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
        project_path: Optional[Union[str, Path]] = None,
        data_path: Optional[Union[str, Path]] = None,
        channel_name: str = 'PFCLFPvsCBEEG',
        remove_artifacts: bool = False,
        filter_type: Optional[str] = None, # If desired, enter the type, eg "butter"
        filter_range: List[float] = [0.5, 4],
        compute_phases: bool = False,
        plot_channel: bool = False,
        plot_spectrogram: bool = False,
        plot_phases: bool = False,
        logging_level: Union[str, int] = "CRITICAL",
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
        
        if headless:
            print("Running in HEADLESS mode. Plotting disabled.", flush=True)
            plot_channel = False
            plot_spectrogram = False
            plot_phases = False
            matplotlib.use('Agg')
        elif hasattr(tkinter, '_default_root') and tkinter._default_root:
            tkinter._default_root.destroy()
            matplotlib.use('Qt5Agg')


        logger = logging.getLogger(__name__)
        logger.setLevel(logging_level)

        # Set the filter boolean based on if filter_type is None
        filter_bool = True if filter_type is not None else False

        try:
            experiment_data_manager = ExperimentDataManager(
                line_num,
                project_path=project_path,
                data_path=data_path,
                logging_level=logging_level,
            )
        except FileNotFoundError as e:
            raise DataNotFoundError(
                "Project metadata files were not found for ephys run.",
                stage="load_experiment_metadata",
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                hint="Ensure project_path points to a directory containing experiments.csv.",
            ) from e
        except Exception as e:
            raise PipelineExecutionError(
                "Failed to initialize ExperimentDataManager for ephys run.",
                stage="load_experiment_metadata",
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                hint="Check metadata formatting and path configuration.",
            ) from e

        # Extract the one relevant piece of information that EphysDataManager needs from metadata--the path to the ephys directory
        ephys_directory = experiment_data_manager.get_ephys_directory()
        
        # Verify we downloaded the Ephys Data
        experiments_csv = experiment_data_manager.project_path / "experiments.csv"
        try:
            file_downloader.verify_file_by_line(
                line_num=line_num,
                csv_path=experiments_csv,
                do_type="ephys",
                base_file_path=experiment_data_manager.data_path,
            )
        except Exception as e:
            raise PipelineExecutionError(
                "Ephys data verification failed.",
                stage="verify_ephys_data",
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                hint="Confirm ephys files are present and accessible from metadata paths.",
            ) from e

        if ephys_directory is None:
             raise ValueError("Ephys directory could not be determined from experiment metadata.")

        # Create instance of EphysDataManager, process the block into channels
        try:
            self.ephys_data_manager = EphysDataManager.create(
                ephys_directory=ephys_directory,
                auto_import_ephys_block=True,
                auto_process_block=False,
                auto_compute_phases=False,
            )
            self.ephys_data_manager.process_ephys_block_to_channels(
                remove_artifacts=remove_artifacts,
                channels=[channel_name],
            )
        except Exception as e:
            raise PipelineExecutionError(
                "Failed to import/process ephys block into channels.",
                stage="process_ephys_block",
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                hint="Verify ephys channel metadata and raw recording format compatibility.",
            ) from e

        logger.debug(self.ephys_data_manager.channels)

        # If filter_type is not None, filter the signal and add it to ephys_data_manager.channels[channel_name].signal_filtered
        if filter_bool:
            print(f'Filtering ephys data with filter type "{filter_type}" and cut {filter_range}')
            try:
                self.ephys_data_manager.filter_ephys(
                    channel_name,
                    ftype=str(filter_type),
                    cut=filter_range,
                    replace_signal=False,
                )
            except Exception as e:
                raise PipelineExecutionError(
                    "Ephys filtering failed.",
                    stage="filter_ephys",
                    line_num=line_num,
                    project_path=project_path,
                    data_path=data_path,
                    hint="Check filter_type/filter_range for valid values.",
                ) from e
        
        if compute_phases:
            # Compute phases after filtering
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

        # Extract correct channel and visualize
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
            channel_worker.plot_channel(use_filtered = filter_bool)

        if plot_spectrogram:
            channel_worker.plot_spectrogram(use_filtered = filter_bool, plot_events=False)  
            
        if plot_phases:
            channel_worker.plot_phases()
            


    def run_all_channels(
        self, 
        line_num: int,
        remove_artifacts: bool = False,
        filter_type: Optional[str] = None, # if desired, enter the type, eg "butter"
        filter_range: List[float] = [0.5, 4],
        plot_channel: bool = False,
        plot_spectrogram: bool = False,
        logging_level: Union[str, int] = "CRITICAL"
    ) -> None:
        """Run ephys analysis pipeline for all channels in an experiment.
        
        Iterates through all channels listed in the experiment metadata
        and performs the analysis workflow on each.
        
        Args:
            line_num: Experiment line number in experiments.csv.
            remove_artifacts: If True, apply artifact removal.
            filter_type: Filter type ('butter', 'fir') or None to skip.
            filter_range: [low, high] cutoff frequencies for bandpass.
            plot_channel: If True, plot time-domain signals.
            plot_spectrogram: If True, plot spectrograms.
            logging_level: Logging verbosity.
        """
        

        logger = logging.getLogger(__name__)
        logger.setLevel(logging_level)
        
        # set the filter boolean based on if filter_type is None
        filter: bool = True if filter_type is not None else False

        experiment_data_manager = ExperimentDataManager(line_num, logging_level = logging_level)

        if experiment_data_manager.metadata is None:
             raise ValueError(f"Metadata could not be loaded for line {line_num}")
        channels_str = experiment_data_manager.metadata['LFP and EEG CSCs']
        channels_list: List = [*channels_str] # unpack
        
        ephys_directory = experiment_data_manager.get_ephys_directory()





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
    
    from aceneurotools.shared.config_utils import load_analysis_params
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