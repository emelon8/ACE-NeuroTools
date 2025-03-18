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
        

        dm = MiniscopeDataManager()
        p = MinicopeProcessor(dm.)

        # this is tough.  

        
    
    
    
    
    
    
    
    
    
    
    
    