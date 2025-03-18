#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""

from src2.ephys.ephys_data_manager import EphysDataManager
from src2.ephys.visualizer import Visualizer
from src2.shared.experiment_data_manager import ExperimentDataManager
from typing import List
import logging



class EphysAPI:
    """Main workflow class."""

    def __init__(self):
        pass
    
    def run(
            self, 
            line_num,
            channel_name = 'PFCLFPvsCBEEG', # could enter "all"
            remove_artifacts = False,
            filter_type = None, # if desired, enter the type, eg "butter"
            filter_range = [0.5, 4],
            plot_channel = False,
            plot_spectrogram = False,
            logging_level = "CRITICAL"
            ):
        
        logger = logging.getLogger(__name__)
        logger.setLevel(logging_level)
        
        # set the filter boolean based on if filter_type is None
        filter: bool = True if filter_type is not None else False

        experiment_data_manager = ExperimentDataManager(line_num, logging_level = logging_level)

        # Set channels_list to be the name of the channel_name provided.  If channel_name is 'all', take values from the 'LFP and...' cell
        channels_list: List 
        if channel_name == 'all':
            metadata = experiment_data_manager.metadata['LFP and EEG CSCs']
            channels_list = [*metadata] # unpack
        else:
            channels_list = [channel_name]

        # Extract the one relevant piece of information that EphysDataManager needs from metadata--the path to the ephys directory
        ephys_directory = experiment_data_manager.metadata['ephys directory']
        
        # Create instance of EphysDataManager, process the block into channels
        ephys_data_manager = EphysDataManager(ephys_directory, auto_import_ephys_block=True, auto_process_block=False)
        ephys_data_manager.process_ephys_block_to_channels(remove_artifacts=remove_artifacts, channels = [channels_list])

        logger.debug(ephys_data_manager.channels)

        # If filter_type is not None, filter the signal and add it to ephys_data_manager.channels[channel_name].signal_filtered
        if filter:
            for channel_name in channels_list:
                ephys_data_manager.filter_ephys(channel_name, ftype=filter_type, cut = filter_range, replace_signal=False)

        # Initialize visualizer
        visualizer = Visualizer(level = logging_level)

        # Extract correct channel and visualize
        for channel_name in channels_list:
            logger.info(f"Visualizing channel: {channel_name}")
            channel = ephys_data_manager.channels[channel_name]

            if plot_channel:
                visualizer.plot_channel(channel, use_filtered = filter)

            if plot_spectrogram:
                visualizer.plot_spectrogram(channel, use_filtered = filter)    





if __name__ == "__main__":
    e = EphysAPI()
    e.run(
          line_num=97,
          channel_name = 'PFCLFPvsCBEEG',
        #   channel_name = 'all',
          remove_artifacts=True,
          filter_type = "butter",
          filter_range = [0.3,0.5],
          plot_channel = True,
         plot_spectrogram = True,
         logging_level="DEBUG"
    )
    # main()
    
    
    
    
    
    
    
    
    
    
    