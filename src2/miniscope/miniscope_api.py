#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""

from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
from src2.miniscope.miniscope_processor import MiniscopeProcessor
from src2.ephys.visualizer import Visualizer
from typing import List

from src2.shared.experiment_data_manager import ExperimentDataManager



class MiniscopeAPI:
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
        

        experiment_data_manager = ExperimentDataManager(line_num, logging_level = logging_level)

        # Extract the one relevant piece of information that EphysDataManager needs from metadata--the path to the ephys directory
        miniscope_directory = experiment_data_manager.get_miniscope_directory()
        analysis_params = experiment_data_manager.analysis_params
        
        # Create instance of EphysDataManager, process the block into channels
        miniscope_data_manager = MiniscopeDataManager(miniscope_directory, analysis_params, auto_import_ephys_block=True, auto_process_block=False)
        
        dm = MiniscopeDataManager()
        # p = MinicopeProcessor(dm.)

        # this is tough.  

        
    
    
    
    
    
    
    
    
    
    
    
    