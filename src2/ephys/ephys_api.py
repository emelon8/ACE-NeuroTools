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
        
        filter = False
        if filter_type is not None:
            filter = True

        dm = ExperimentDataManager(line_num, logging_level = logging_level)

        channels_list: List
        if channel_name == 'all':
            channels_list = dm.metadata['LFP and EEG CSCs']
        else:
            channels_list = channel_name

        ephys_directory = dm.metadata['ephys directory']
        
        edm = EphysDataManager(ephys_directory, auto_import_ephys_block=True, auto_process_block=False)

        edm.process_ephys_block_to_channels(remove_artifacts=remove_artifacts, channels = [channels_list])

        if filter:
            edm.filter_ephys(channel_name, ftype=filter_type, cut = filter_range, replace_signal=False)

        channel = edm.channels[channel_name]

        v = Visualizer(channel, level = logging_level)


        if plot_channel:
            v.plot_channel(use_filtered = filter)

        if plot_spectrogram:
            v.plot_spectrogram(use_filtered = filter)    

        

if __name__ == "__main__":
    e = EphysAPI()
    e.run(
          line_num=97,
          channel_name = 'PFCLFPvsCBEEG',
          remove_artifacts=True,
          filter_type = "butter",
          filter_range = [0.3,0.5],
          plot_channel = True,
         plot_spectrogram = True,
         logging_level="DEBUG"
    )
    # main()
    
    
    
    
    
    
    
    
    
    
    