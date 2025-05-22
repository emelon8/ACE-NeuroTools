#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 21 11:49:30 2025

@author: nathan
"""

# Set the current working directory to this script's directory
import os

import matplotlib
from src2.miniscope.miniscope_api import MiniscopeAPI
from src2.ephys.ephys_api import EphysAPI
from src2.multimodal.miniscope_ephys_alignment_utils import syncNeuralynxMiniscopeTimestamps

class MultimodalAPI:
        
    
    def run(self,
            #line number of experiment you are analyzing
            line_num,   
            
            #ephys parameters
            channel_name = 'PFCLFPvsCBEEG',
            remove_artifacts = False,
            filter_type = None, # if desired, enter the type, eg "butter"
            filter_range = [0.5, 4],
            plot_channel = False,
            plot_spectrogram = False,
            logging_level = "CRITICAL",
            
            #miniscope parameters:
            #preprocessing
            crop = True,
                #These should only be true/contain values if crop=True
                crop_square = False,
                crop_with_crop = False,
                crop_with_gui = True,
            detrend = True,
            df_over_f = True,

            #processing parameters    
            parallel = False,
            n_processes = 6,
            apply_motion_correction = True,
            inspect_motion_correction = True,
            inspect_corr_PNR = True,
            downsample_for_corr_PNR = 1,
            run_CNMFE = True,
            save_CNMFE_estimates_filename = 'estimates.hdf5',
            
            #post-processing parameters
            remove_components_with_gui=True, 
            evaluate_components=False, 
            find_calcium_events=True, 
            compute_miniscope_spectrogram=True, 
            compute_miniscope_phase=True, 
            filter_miniscope_data=True
            ):
        
        ephys_api = EphysAPI()
        ephys_api.run(line_num, channel_name, remove_artifacts, filter_type, filter_range, plot_channel, plot_spectrogram, logging_level)
        
        miniscope_api = MiniscopeAPI()

        print(f"In the multimodal api, this is what we are passing in for save_estimates_filename: {save_CNMFE_estimates_filename}")
        miniscope_api.run(line_num, crop, crop_square, crop_with_crop, crop_with_gui, detrend, df_over_f, parallel, n_processes, 
                          apply_motion_correction, inspect_motion_correction, inspect_corr_PNR, downsample_for_corr_PNR, run_CNMFE, 
                         save_CNMFE_estimates_filename, remove_components_with_gui, evaluate_components, find_calcium_events, 
                          compute_miniscope_spectrogram, compute_miniscope_phase, filter_miniscope_data)

        
        #pull everything we need to run miniscope_ephys.py:
        tCaIm, low_confidence_periods, channel, miniscope_dm = syncNeuralynxMiniscopeTimestamps(
                        ephys_api.ephys_data_manager.get_channel(channel_name),
                        miniscope_api.miniscope_data_manager,
                        True,
                        True,
                        True)
        
        # set changed variables
        print("\nSuccess! Setting changed variables.")
        miniscope_api.data_manager = miniscope_dm
        ephys_api.ephys_data_manager.channels[channel_name] = channel
        
        
        
        


if __name__ == "__main__":
    matplotlib.use('Agg')
    # run the API
    api = MultimodalAPI()
    api.run(
        line_num = 97, #line number of the experiment you are analyzing
        #ephys parameters
        channel_name = 'PFCLFPvsCBEEG',
        remove_artifacts = False,
        filter_type = None, # if desired, enter the type, eg "butter"
        filter_range = [0.5, 4],
        plot_channel = False,
        plot_spectrogram = False,
        logging_level = "CRITICAL",
        
        #preprocessing parameters
        crop = False,
            #These should only be true/contain values if crop=True
            crop_square = False,
            crop_with_crop = False,
            crop_with_gui = False,
        detrend = True,
        df_over_f = True,

        #processing parameters    
        parallel = False,
        n_processes = 6,
        apply_motion_correction = False,
        inspect_motion_correction = False,
        inspect_corr_PNR = False,
        downsample_for_corr_PNR = 1,
        run_CNMFE = True,
        save_CNMFE_estimates_filename = 'estimates.hdf5',
        
        #post-processing parameters
        remove_components_with_gui=False, 
        evaluate_components=False, 
        find_calcium_events=True, 
        compute_miniscope_spectrogram=True, 
        compute_miniscope_phase=True, 
        filter_miniscope_data=True)