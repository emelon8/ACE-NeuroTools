#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""

from src2.ephys_data_manager import EphysDataManager
from src2.visualizer import Visualizer



class EphysWorkflow:
    """Main workflow class."""

    def __init__(self, line_num):
        self.dm = EphysDataManager(line_num)
        self.dm.import_ephys_block()
        self.dm.process_ephys_block_to_channels()
    
    def run_analysis(self, channel_name='PFCLFPvsCBEEG'):

        channel = self.dm.channels[channel_name]

        v = Visualizer(channel)

        v.plot_channel()
        v.plot_spectrogram()
    

    def run_workflow2(self):
        pass
    
    
    
    
    
    
    
    
    
    
    
    
    