#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""

from src2.ephys.channel_worker import ChannelWorker
from src2.ephys.ephys_data_manager import EphysDataManager
from src2.ephys.visualizer import Visualizer
from src2.shared.experiment_data_manager import ExperimentDataManager
from src2.shared.paths import DATA_DIR
from typing import List
from src2.shared import file_downloader
import logging
import argparse
import sys
import yaml
import matplotlib
import tkinter
from src2.shared.config_utils import load_config, parse_ephys_config


class EphysAPI:
    """High-level API for electrophysiology data analysis workflows.
    
    Provides simplified methods for loading, filtering, and visualizing
    Neuralynx ephys data with configurable analysis parameters.
    
    Attributes:
        ephys_data_manager: EphysDataManager instance (set after run()).
    """

    def __init__(self):
        """Initialize the EphysAPI."""
        pass
    


    def run(
            self, 
            line_num,
            channel_name = 'PFCLFPvsCBEEG',
            remove_artifacts = False,
            filter_type = None, # If desired, enter the type, eg "butter"
            filter_range = [0.5, 4],
            compute_phases = False,
            plot_channel = False,
            plot_spectrogram = False,
            plot_phases = False,
            logging_level = "CRITICAL",
            headless = False
            ):
        """Run the ephys analysis pipeline for a single channel.
        
        Loads ephys data, optionally filters and computes phases, and
        generates plots based on the provided parameters.
        
        Args:
            line_num: Experiment line number in experiments.csv.
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
        elif tkinter._default_root:
            tkinter._default_root.destroy()
            matplotlib.use('Qt5Agg')

        logger = logging.getLogger(__name__)
        logger.setLevel(logging_level)

        # Set the filter boolean based on if filter_type is None
        filter_bool = True if filter_type is not None else False

        experiment_data_manager = ExperimentDataManager(line_num, logging_level = logging_level)

        # Extract the one relevant piece of information that EphysDataManager needs from metadata--the path to the ephys directory
        ephys_directory = experiment_data_manager.get_ephys_directory()
        
        # Verify we downloaded the Ephys Data
        file_downloader.verify_file_by_line(line_num=line_num, csv_path=DATA_DIR/"experiments.csv",do_type="ephys")

        # Create instance of EphysDataManager, process the block into channels
        self.ephys_data_manager = EphysDataManager(ephys_directory, auto_import_ephys_block=True, auto_process_block=False, auto_compute_phases=False)
        self.ephys_data_manager.process_ephys_block_to_channels(remove_artifacts=remove_artifacts, channels = channel_name)


        logger.debug(self.ephys_data_manager.channels)

        # If filter_type is not None, filter the signal and add it to ephys_data_manager.channels[channel_name].signal_filtered
        if filter_bool:
            print('Filtering eohys data with filter type "{filter_type}" and cut {filter_range}')
            self.ephys_data_manager.filter_ephys(channel_name, ftype=filter_type, cut = filter_range, replace_signal=False)
        
        if compute_phases:
            # Compute phases after filtering
            self.ephys_data_manager.compute_phases_all_channels()

        # Extract correct channel and visualize
        logger.info(f"Visualizing channel: {channel_name}")
        channel = self.ephys_data_manager.get_channel(channel_name)
        channel_worker = ChannelWorker(channel)
        

        if plot_channel:
            channel_worker.plot_channel(use_filtered = filter_bool)

        if plot_spectrogram:
            channel_worker.plot_spectrogram(use_filtered = filter_bool, plot_events=False)  
            
        if plot_phases:
            channel_worker.plot_phases()
            

    def run_all_channels(
            self, 
            line_num,
            remove_artifacts = False,
            filter_type = None, # if desired, enter the type, eg "butter"
            filter_range = [0.5, 4],
            plot_channel = False,
            plot_spectrogram = False,
            logging_level = "CRITICAL"
            ):
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

        channels_str = experiment_data_manager.metadata['LFP and EEG CSCs']
        channels_list: List = [*channels_str] # unpack




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Ephys Analysis Pipeline")
    parser.add_argument('--config', type=str, help="Path to YAML configuration file")
    parser.add_argument('--headless', action='store_true', help="Run in headless mode (no GUI)")
    
    args = parser.parse_args()
    
    # Default parameters
    run_params = {
        'line_num': 101,
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
    
    if args.config:
        print(f"Loading configuration from {args.config}...", flush=True)
        config = load_config(args.config)
        config_params = parse_ephys_config(config)
        run_params.update(config_params)
        
    if args.headless:
        run_params['headless'] = True

    e = EphysAPI()
    try:
        e.run(**run_params)
    except Exception as e:
        print(f"Error occurred during execution: {e}", file=sys.stderr)
        if args.headless:
            sys.exit(1)
        raise