#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""

from src2.ephys.ephys_data_manager import EphysDataManager
from src2.ephys.visualizer import Visualizer
from typing import List



class EphysWorkflow:
    """Main workflow class."""

    def __init__(self):
        pass
    
    def run(
            self, 
            line_num,
            channel_name = 'PFCLFPvsCBEEG',
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

        dm = EphysDataManager(line_num, auto_import_ephys_block=False, auto_process_block=False)
        dm.import_ephys_block()
        dm.process_ephys_block_to_channels(remove_artifacts=remove_artifacts, channels = [channel_name])
        if filter:
            dm.filter_ephys(channel_name, ftype=filter_type, cut = filter_range, replace_signal=False)

        channel = dm.channels[channel_name]

        v = Visualizer(channel, level = logging_level)


        if plot_channel:
            v.plot_channel(use_filtered = filter)

        if plot_spectrogram:
            v.plot_spectrogram(use_filtered = filter)    

        
    
    
    
    
    
    
    
    
    
    
    
    